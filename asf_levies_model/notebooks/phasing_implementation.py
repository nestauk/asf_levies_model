# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     comment_magics: true
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: asf_levies_model
#     language: python
#     name: python3
# ---

# %% [markdown]
# ### Implementing rebalancing through phasing

# %% [markdown]
# **What we want to do:**
# - Implement rebalancing RO and FIT from electricity to gas in three phases over three price cap periods
#
# **What we need for this:**
# - For each price cap period (period 0, period 1 (rebalancing phase 1), period 2 (rebalancing phase 2), period 3 (rebalancing phase 3))
#     - Create a LevyCollection specific to that period (status_quo_pc)
#     - If rebalancing period: Apply the partial rebalancing to that LevyCollection (rebalanced_pc)
#     - Create electricity and gas Tariffs specific to that period (status_quo_tariff; if rebalancing period: rebalanced_tariff)
#     - Create ConsumerCollection using mean consumption (status_quo_consumers, rebalanced_consumers)
#     - Apply support (£150 WHD rebate in status quo, TBC in rebalanced)
#
# **What do we want to know:**
# - For each Consumer:
#     - Bill change from period n-1 to n
#
# **Price cap periods to model**
# - n = 0. Jul-Sep 2023
# - n = 1. Oct-Dec 2023 (price cap fall) (phase rebalancing: move FiT to gas)
# - n = 2. Jan-Mar 2024 (price cap rise) (phase rebalancing: moved FiT to gas)
# - n = 3. Apr-Jun 2024 (price cap fall) (phase rebalancing: moved FiT to gas, move 1/2 RO to gas)
# - n = 4. Jul-Sep 2024 (price cap fall) (phase rebalancing: moved FiT to gas, move all of RO to gas)
#
# **How to phase changes to support**
#
# Increases to WHD revenue at each phase reflects the proportion of the revenue moved from electricity to gas in the phase out of all revenue to be moved. This is then applied to the difference between status quo whd core spending and the desired whd core spending of £1.6bn. Unit discounts are then calculated from that whd revenue total for the phase.

# %% [markdown]
# ### Set up

# %%
import pandas as pd
from datetime import datetime
import copy
import numpy as np
import matplotlib.pyplot as plt

import asf_levies_model.levies as levies
import asf_levies_model.tariffs as tariffs
from asf_levies_model.consumers import Consumer, ConsumerCollection
import asf_levies_model.getters.load_data as data
from asf_levies_model.summary import create_scenario_weights_dict
from asf_levies_model.utils.utils import create_eligibility_group_sizes_dictionary
from asf_levies_model import PROJECT_DIR

# %% [markdown]
# **Universal parameters**

# %%
# Denominator values from Desnz subnational consumption domestic data, 2023
supply_elec = 96_517_461
supply_gas = 266_505_188
customers_gas = 24_605_467
customers_elec = 29_239_936

denominator_values = {
    "supply_elec": supply_elec,
    "supply_gas": supply_gas,
    "customers_gas": customers_gas,
    "customers_elec": customers_elec,
}

total_supply_elec = (
    249_044_438  # DESNZ GB total electricity consumption - all meters (2023)
)

ofgem_archetypes_df = data.ofgem_archetypes_data()

target_whd_core_spend = 1_600_000_000
whd_industry_initiatives = 50_000_000

# Pinning target recipients to value at time 0
# whd_core_target_recipients = (545_000_000 - whd_industry_initiatives) / 150

# %% [markdown]
# **Scheme Eligibility Sizes**

# %%
# Load CWP sizes
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()
total_cwp_group = ofgem_archetypes_scheme_eligibility_df["CWPEligibleSize"].sum()

cwp_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="CWPEligibleSize",
)

# WHD eligibility sizes
# For scenario description purposes only
# total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()
# whd_sizes = create_eligibility_group_sizes_dictionary(
#     df=ofgem_archetypes_scheme_eligibility_df,
#     group_name_col="AnnualConsumptionProfile",
#     total_size_col="ArchetypeSize",
#     eligible_size_col="WHDEligibleSize",
# )

# # Scale eligible group sizes down to WHD core target recipients
# scaling_factor = whd_core_target_recipients / total_whd_group
# scaling_factor_remainder = 1 - scaling_factor
# scaled_whd_sizes = {
#     k: {
#         True: (v[True] * scaling_factor),
#         False: v[False] + (v[True] * scaling_factor_remainder),
#     }
#     for k, v in whd_sizes.items()
# }

# %% [markdown]
# ### Price cap period n = 0: July - September 2023

# %% [markdown]
# **1. Set up policy costs**

# %%
price_cap_0 = "2023-07-01"

# %%
# Scaling factor for estimating domestic share of FIT revenue
exempt_eii_supply = 9_655_302  # July-Sep 2023 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(
        data.process_data_RO(fileobject), denominator=supply_elec, price_cap=price_cap_0
    ),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject),
        denominator=supply_elec,
        price_cap=price_cap_0,
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject),
        denominator=customers_gas,
        price_cap=price_cap_0,
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        price_cap=price_cap_0,
    ),
    levies.ECO4.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_0
    ),  # Split ECO
    levies.GBIS.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_0
    ),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
        price_cap=price_cap_0,
    ),
]
fileobject.close()

price_cap_0_pc = levies.LevyCollection(
    "Policy Costs", "pc", list_levies, denominator_values
)

# Rebalance to denominators
price_cap_0_pc = price_cap_0_pc.rebalance_to_denominators()

# %% [markdown]
# **2. Implement rebalancing phase**
#
# N/A for this period

# %% [markdown]
# **3. Set up tariffs**

# %%
# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
    price_cap=price_cap_0,
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
    price_cap=price_cap_0,
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
price_cap_0_gas_tariff = gas_tariff.update_policy_costs(price_cap_0_pc)
price_cap_0_electricity_tariff = electricity_tariff.update_policy_costs(price_cap_0_pc)

# %%
# Check price cap in Annex 9 (£1975.94)
price_cap_0_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + price_cap_0_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# **4. Set up ConsumerCollection**

# %%
price_cap_0_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=price_cap_0_gas_tariff,
    electricity_tariff=price_cap_0_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

price_cap_0_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=True
)

# %% [markdown]
# ### Price cap period n = 1: October - December 2023
#
# The price cap fell in this period, so we can phase the first part of rebalancing.

# %% [markdown]
# **1. Set up policy costs**

# %%
price_cap_1 = "2023-10-01"

# %%
# Scaling factor for estimating domestic share of FIT revenue
exempt_eii_supply = 9_404_573  # Oct-Dec2023 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(
        data.process_data_RO(fileobject), denominator=supply_elec, price_cap=price_cap_1
    ),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject),
        denominator=supply_elec,
        price_cap=price_cap_1,
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject),
        denominator=customers_gas,
        price_cap=price_cap_1,
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        price_cap=price_cap_1,
    ),
    levies.ECO4.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_1
    ),  # Split ECO
    levies.GBIS.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_1
    ),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
        price_cap=price_cap_1,
    ),
]
fileobject.close()

price_cap_1_pc = levies.LevyCollection(
    "Policy Costs", "pc", list_levies, denominator_values
)

# Rebalance to denominators
price_cap_1_pc = price_cap_1_pc.rebalance_to_denominators()

# %% [markdown]
# **2. Implement rebalancing phase**
#
# Rebalancing: Rebalance FiT from electricity to gas

# %%
# Create rebalancing weights for RO and FiT
rebalancing_weights_fit = create_scenario_weights_dict(price_cap_1_pc)
for levy in price_cap_1_pc[["fit"]]:
    rebalancing_weights_fit[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# Apply rebalancing
rebalanced_price_cap_1_pc = price_cap_1_pc.rebalance_levies(
    rebalancing_weights_fit, scenario_name="rebalance_fit_to_gas"
)

# %% [markdown]
# Support: Proportional Increase to WHD Revenue

# %%
# FiT proportion of proposed rebalancing
rebalanced_price_cap_1_support_prop = rebalanced_price_cap_1_pc["fit"].revenue / (
    rebalanced_price_cap_1_pc["fit"].revenue + rebalanced_price_cap_1_pc["ro"].revenue
)
rebalanced_price_cap_1_support_prop

# %%
# Price cap difference in WHD to target.

# Calculate additional whd revenue commitment as:
# (target whd core spend - current whd core spend) * rebalancing proportion
rebalanced_price_cap_1_additional_whd_revenue = (
    target_whd_core_spend
    - (rebalanced_price_cap_1_pc["whd"].revenue - whd_industry_initiatives)
) * rebalanced_price_cap_1_support_prop
rebalanced_price_cap_1_additional_whd_revenue

# %%
# Update the whd revenue
rebalanced_price_cap_1_pc = rebalanced_price_cap_1_pc.update_revenues(
    {
        "whd": rebalanced_price_cap_1_pc["whd"].revenue
        + rebalanced_price_cap_1_additional_whd_revenue
    }
)

# %%
# new levy rates
price_cap_1_pc["whd"].electricity_fixed_rate, rebalanced_price_cap_1_pc[
    "whd"
].electricity_fixed_rate

# %% [markdown]
# Support: Calculate Discount rate

# %%
# Estimate total electricity and gas consumption of all eligible households across archetypes
# NB doesn't matter which consumers we use for this as they're constant over the model.
# as a result, we also only need to do this bit once.
cwp_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in price_cap_0_consumers.iter_eligible()
)
cwp_recipients_gas_consumption = sum(
    consumer.gas_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in price_cap_0_consumers.iter_eligible()
)

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
cwp_core_target_spending_electricity_weight = cwp_recipients_electricity_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)
cwp_core_target_spending_gas_weight = cwp_recipients_gas_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)

# %%
# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    rebalanced_price_cap_1_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_electricity_weight
core_target_spending_gas = (
    rebalanced_price_cap_1_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_electricity = (
    (core_target_spending_electricity) / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
unit_discount_gas = (
    core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# %%
# 1.14p per kwh discount
print(unit_discount_electricity, unit_discount_gas)

# %% [markdown]
# **3. Set up tariffs**

# %% [markdown]
# Status quo

# %%
# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
    price_cap=price_cap_1,
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
    price_cap=price_cap_1,
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
price_cap_1_gas_tariff = gas_tariff.update_policy_costs(price_cap_1_pc)
price_cap_1_electricity_tariff = electricity_tariff.update_policy_costs(price_cap_1_pc)

# %%
# Check price cap in Annex 9 (£1834.02)
price_cap_1_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + price_cap_1_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# Rebalanced

# %%
# Update policy costs with partially rebalanced policy costs
rebalanced_price_cap_1_gas_tariff = gas_tariff.update_policy_costs(
    rebalanced_price_cap_1_pc
)
rebalanced_price_cap_1_electricity_tariff = electricity_tariff.update_policy_costs(
    rebalanced_price_cap_1_pc
)

# %%
# Check price cap under rebalancing
rebalanced_price_cap_1_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + rebalanced_price_cap_1_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# **4. Set up ConsumerCollection**

# %%
price_cap_1_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=price_cap_1_gas_tariff,
    electricity_tariff=price_cap_1_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

price_cap_1_consumers = price_cap_1_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=False
)

# %%
rebalanced_price_cap_1_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=rebalanced_price_cap_1_gas_tariff,
    electricity_tariff=rebalanced_price_cap_1_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

rebalanced_price_cap_1_consumers = (
    rebalanced_price_cap_1_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %% [markdown]
# ### Price cap period n = 2: January - March 2024

# %% [markdown]
# **1. Set up policy costs**

# %%
price_cap_2 = "2024-01-01"

# %%
# Scaling factor for estimating domestic share of FIT revenue
exempt_eii_supply = 9_404_573  # Jan-Mar2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(
        data.process_data_RO(fileobject), denominator=supply_elec, price_cap=price_cap_2
    ),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject),
        denominator=supply_elec,
        price_cap=price_cap_2,
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject),
        denominator=customers_gas,
        price_cap=price_cap_2,
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        price_cap=price_cap_2,
    ),
    levies.ECO4.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_2
    ),  # Split ECO
    levies.GBIS.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_2
    ),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
        price_cap=price_cap_2,
    ),
]
fileobject.close()

price_cap_2_pc = levies.LevyCollection(
    "Policy Costs", "pc", list_levies, denominator_values
)

# Rebalance to denominators
price_cap_2_pc = price_cap_2_pc.rebalance_to_denominators()

# %% [markdown]
# **2. Implement rebalancing phase**
#
# Rebalancing: Rebalance FiT from electricity to gas

# %%
# Apply rebalancing
rebalanced_price_cap_2_pc = price_cap_2_pc.rebalance_levies(
    rebalancing_weights_fit, scenario_name="rebalance_fit_to_gas"
)

# %% [markdown]
# Support: Update WHD revenue

# %%
# Update the whd revenue
# assume underlying revenue doesn't change between price caps (it doesn't in this case)
rebalanced_price_cap_2_pc = rebalanced_price_cap_2_pc.update_revenues(
    {"whd": rebalanced_price_cap_1_pc["whd"].revenue}
)

# %% [markdown]
# Support: Unit discount rates
#
# Carried over from prior price cap, no change.

# %% [markdown]
# **3. Set up tariffs**

# %%
# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
    price_cap=price_cap_2,
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
    price_cap=price_cap_2,
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
price_cap_2_gas_tariff = gas_tariff.update_policy_costs(price_cap_2_pc)
price_cap_2_electricity_tariff = electricity_tariff.update_policy_costs(price_cap_2_pc)

# %%
# Check price cap in Annex 9 (£1928.34)
price_cap_2_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + price_cap_2_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# Rebalanced

# %%
# Update policy costs with partially rebalanced policy costs
rebalanced_price_cap_2_gas_tariff = gas_tariff.update_policy_costs(
    rebalanced_price_cap_2_pc
)
rebalanced_price_cap_2_electricity_tariff = electricity_tariff.update_policy_costs(
    rebalanced_price_cap_2_pc
)

# %%
# Check price cap under rebalancing
rebalanced_price_cap_2_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + rebalanced_price_cap_2_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# **4. Set up ConsumerCollection**

# %%
price_cap_2_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=price_cap_2_gas_tariff,
    electricity_tariff=price_cap_2_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

price_cap_2_consumers = price_cap_2_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=False
)

# %%
rebalanced_price_cap_2_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=rebalanced_price_cap_2_gas_tariff,
    electricity_tariff=rebalanced_price_cap_2_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

rebalanced_price_cap_2_consumers = (
    rebalanced_price_cap_2_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %% [markdown]
# ### Price cap period n = 3: April - June 2024
#
# The price cap fell in this period, so we can phase the second part of rebalancing.

# %% [markdown]
# **1. Set up policy costs**

# %%
price_cap_3 = "2024-04-01"

# %%
# Scaling factor for estimating domestic share of FIT revenue
exempt_eii_supply = 9_400_038  # Apr-Jun2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(
        data.process_data_RO(fileobject), denominator=supply_elec, price_cap=price_cap_3
    ),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject),
        denominator=supply_elec,
        price_cap=price_cap_3,
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject),
        denominator=customers_gas,
        price_cap=price_cap_3,
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        price_cap=price_cap_3,
    ),
    levies.ECO4.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_3
    ),  # Split ECO
    levies.GBIS.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_3
    ),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
        price_cap=price_cap_3,
    ),
]
fileobject.close()

price_cap_3_pc = levies.LevyCollection(
    "Policy Costs", "pc", list_levies, denominator_values
)

# Rebalance to denominators
price_cap_3_pc = price_cap_3_pc.rebalance_to_denominators()

# %% [markdown]
# **2. Implement rebalancing phase**
#
# Rebalancing: Rebalance FiT from electricity to gas + Rebalance 1/2 of RO from electricity to gas

# %%
# Add rebalancing of 1/2 of RO to gas to existing dictionary
rebalancing_weights_fit_half_ro = copy.deepcopy(rebalancing_weights_fit)
for levy in price_cap_3_pc[["ro"]]:
    rebalancing_weights_fit_half_ro[levy.short_name] = {
        "new_electricity_weight": 0.5,
        "new_gas_weight": 0.5,
        "new_tax_weight": 0,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# Apply rebalancing
rebalanced_price_cap_3_pc = price_cap_3_pc.rebalance_levies(
    rebalancing_weights_fit_half_ro, scenario_name="rebalance_fit_half_ro_to_gas"
)

# %% [markdown]
# Support: Calculate WHD revenue

# %%
# FiT proportion of proposed rebalancing
rebalanced_price_cap_3_support_prop = (
    rebalanced_price_cap_3_pc["fit"].revenue
    + (rebalanced_price_cap_3_pc["ro"].revenue * 0.5)
) / (rebalanced_price_cap_3_pc["fit"].revenue + rebalanced_price_cap_3_pc["ro"].revenue)
rebalanced_price_cap_3_support_prop

# %%
# Calculate additional whd revenue commitment as:
# (target whd core spend - status quo whd core spend) * rebalancing proportion
rebalanced_price_cap_3_additional_whd_revenue = (
    target_whd_core_spend - (price_cap_3_pc["whd"].revenue - whd_industry_initiatives)
) * rebalanced_price_cap_3_support_prop
rebalanced_price_cap_3_additional_whd_revenue

# %%
# Update the whd revenue
rebalanced_price_cap_3_pc = rebalanced_price_cap_3_pc.update_revenues(
    {
        "whd": price_cap_3_pc["whd"].revenue
        + rebalanced_price_cap_3_additional_whd_revenue
    }
)
rebalanced_price_cap_3_pc["whd"].revenue

# %% [markdown]
# Support: Calculate discount rate

# %%
# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    rebalanced_price_cap_3_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_electricity_weight
core_target_spending_gas = (
    rebalanced_price_cap_3_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_gas_weight

# %%
# Calculate unit discounts for electricity and gas
unit_discount_electricity = (
    (core_target_spending_electricity) / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
unit_discount_gas = (
    core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount


# %%
# 1.86p per kwh discount
print(unit_discount_electricity, unit_discount_gas)

# %% [markdown]
# **3. Set up tariffs**

# %% [markdown]
# Status quo

# %%
# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
    price_cap=price_cap_3,
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
    price_cap=price_cap_3,
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
price_cap_3_gas_tariff = gas_tariff.update_policy_costs(price_cap_3_pc)
price_cap_3_electricity_tariff = electricity_tariff.update_policy_costs(price_cap_3_pc)

# %%
# Check price cap in Annex 9 (£1690.27)
price_cap_3_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + price_cap_3_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# Rebalanced

# %%
# Update policy costs with partially rebalanced policy costs
rebalanced_price_cap_3_gas_tariff = gas_tariff.update_policy_costs(
    rebalanced_price_cap_3_pc
)
rebalanced_price_cap_3_electricity_tariff = electricity_tariff.update_policy_costs(
    rebalanced_price_cap_3_pc
)

# %%
# Check price cap under rebalancing
rebalanced_price_cap_3_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + rebalanced_price_cap_3_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# **4. Set up ConsumerCollection**

# %%
price_cap_3_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=price_cap_3_gas_tariff,
    electricity_tariff=price_cap_3_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

price_cap_3_consumers = price_cap_3_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=False
)

# %%
rebalanced_price_cap_3_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=rebalanced_price_cap_3_gas_tariff,
    electricity_tariff=rebalanced_price_cap_3_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

rebalanced_price_cap_3_consumers = (
    rebalanced_price_cap_3_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %% [markdown]
# ### Price cap period n = 4: July - September 2024
#
# The price cap fell in this period, so we can phase the third part of rebalancing.

# %% [markdown]
# **1. Set up policy costs**

# %%
price_cap_4 = "2024-07-01"

# %%
# Scaling factor for estimating domestic share of FIT revenue
exempt_eii_supply = 9_400_038  # Jul-Sep 2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(
        data.process_data_RO(fileobject), denominator=supply_elec, price_cap=price_cap_4
    ),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject),
        denominator=supply_elec,
        price_cap=price_cap_4,
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject),
        denominator=customers_gas,
        price_cap=price_cap_4,
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        price_cap=price_cap_4,
    ),
    levies.ECO4.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_4
    ),  # Split ECO
    levies.GBIS.from_dataframe(
        data.process_data_ECO(fileobject), price_cap=price_cap_4
    ),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
        price_cap=price_cap_4,
    ),
]
fileobject.close()

price_cap_4_pc = levies.LevyCollection(
    "Policy Costs", "pc", list_levies, denominator_values
)

# Rebalance to denominators
price_cap_4_pc = price_cap_4_pc.rebalance_to_denominators()

# %% [markdown]
# **2. Implement rebalancing phase**
#
# Rebalancing: Rebalance FiT from electricity to gas + Rebalance 1/2 of RO from electricity to gas

# %%
# Add rebalancing of all of RO to gas to existing dictionary
rebalancing_weights_fit_ro = copy.deepcopy(rebalancing_weights_fit)
for levy in price_cap_4_pc[["ro"]]:
    rebalancing_weights_fit_ro[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# Apply rebalancing
rebalanced_price_cap_4_pc = price_cap_4_pc.rebalance_levies(
    rebalancing_weights_fit_ro, scenario_name="rebalance_fit_ro_to_gas"
)

# %%
rebalanced_price_cap_4_additional_whd_revenue = (
    target_whd_core_spend - (price_cap_4_pc["whd"].revenue - whd_industry_initiatives)
) * 1
rebalanced_price_cap_4_additional_whd_revenue

# %%
rebalanced_price_cap_4_pc = rebalanced_price_cap_4_pc.update_revenues(
    {"whd": target_whd_core_spend + whd_industry_initiatives}
)

# %%
# new levy rates
price_cap_4_pc["whd"].electricity_fixed_rate, rebalanced_price_cap_4_pc[
    "whd"
].electricity_fixed_rate

# %% [markdown]
# Support: Calculate discount rate

# %%
# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    rebalanced_price_cap_4_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_electricity_weight
core_target_spending_gas = (
    rebalanced_price_cap_4_pc["whd"].revenue - whd_industry_initiatives
) * cwp_core_target_spending_gas_weight


# %%
# Calculate unit discounts for electricity and gas
unit_discount_electricity = (
    (core_target_spending_electricity) / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
unit_discount_gas = (
    core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# %%
# 2.57p per kwh discount
print(unit_discount_electricity, unit_discount_gas)

# %% [markdown]
# **3. Set up tariffs**

# %% [markdown]
# Status quo

# %%
# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
    price_cap=price_cap_4,
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
    price_cap=price_cap_4,
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
price_cap_4_gas_tariff = gas_tariff.update_policy_costs(price_cap_4_pc)
price_cap_4_electricity_tariff = electricity_tariff.update_policy_costs(price_cap_4_pc)

# %%
# Check price cap in Annex 9 (£1567.96)
price_cap_4_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + price_cap_4_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# Rebalanced

# %%
# Update policy costs with partially rebalanced policy costs
rebalanced_price_cap_4_gas_tariff = gas_tariff.update_policy_costs(
    rebalanced_price_cap_4_pc
)
rebalanced_price_cap_4_electricity_tariff = electricity_tariff.update_policy_costs(
    rebalanced_price_cap_4_pc
)

# %%
# Check price cap under rebalancing
rebalanced_price_cap_4_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + rebalanced_price_cap_4_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %% [markdown]
# **4. Set up ConsumerCollection**

# %%
price_cap_4_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=price_cap_4_gas_tariff,
    electricity_tariff=price_cap_4_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

price_cap_4_consumers = price_cap_4_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=False
)

# %%
rebalanced_price_cap_4_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=rebalanced_price_cap_4_gas_tariff,
    electricity_tariff=rebalanced_price_cap_4_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

rebalanced_price_cap_4_consumers = (
    rebalanced_price_cap_4_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %% [markdown]
# ### **Analysing bill changes**
#
# **What values do we have?**
#
# For price cap period n = 0:
# - Bill value for each archetype
#
# For price cap periods n = 1 to n = 4:
# - Bill value for each archetype *status quo historical*
# - Bill value for each archetype *under phased rebalancing*
#
# **Which variables are of interest to us?**
#
# There are two ways we can measure the net effect of rebalancing.
#
# ***Option 1***
#
# In this option, the bill change is with respect to the archetype's status quo bill in that price cap.
#
# - For each price cap period:
#     - For each archetype:
#         - Bill change = (Bill under rebalancing) - (Status quo bill)
#
#
# ***Option 2 (what is plotted in the above bars)***
#
# In this option, the bill change is with respect to the archetype's bill in the *previous* price cap, and there are two independent parallel series of bills we are tracking (status quo and under rebalancing).
#
# - For each price cap period n:
#     - For each archetype:
#         - Status quo series bill change = (Status quo bill in price cap period n) - (Status quo bill in price cap period n-1)
#         - Rebalanced series bill change = (Rebalanced bill in price cap period n) - (Rebalanced bill in price cap period n-1)
#         - Bill change from price cap change only = Status quo series bill change (blue bars)
#         - Effect of rebalancing on bill change = Rebalanced series bill change - Status quo series bill change (red bars)
#         - Rebalanced series bill change as net bill change (black dot)

# %% [markdown]
# #### **Price cap period n = 1: October - December 2023**

# %% [markdown]
# **1. Bill change with respect to the status quo bill**

# %%
price_cap_1_change_wrt_sq = {}

for consumer_sq, consumer_rb in zip(
    price_cap_1_consumers, rebalanced_price_cap_1_consumers
):
    price_cap_1_change_wrt_sq[consumer_sq.archetype] = (
        consumer_rb.combined_fuel_bill - consumer_sq.combined_fuel_bill
    )

# %%
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    list(price_cap_1_change_wrt_sq.keys()),
    list(price_cap_1_change_wrt_sq.values()),
    color="#FF9999",
)

# Styling
ax.set_ylabel("Difference in annual energy bill with respect to status quo")
ax.set_xlabel("Archetype")
ax.set_title("Effect of rebalancing on annual energy bill in (Oct-Dec 2023)")
ax.grid(True, linestyle="--", alpha=0.7)

archetypes = [consumer.archetype for consumer in price_cap_0_consumers]
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# **2. Bill change with respect to the bill under previous price cap**

# %%
# Under no rebalancing
bill_changes_0_to_1 = {}
for consumer0, consumer1 in zip(price_cap_0_consumers, price_cap_1_consumers):
    bill_changes_0_to_1[consumer0.archetype] = (
        consumer1.combined_fuel_bill - consumer0.combined_fuel_bill
    )

# %%
# With partial rebalancing
rebalanced_bill_changes_0_to_1 = {}
for consumer0, consumer1 in zip(
    price_cap_0_consumers, rebalanced_price_cap_1_consumers
):
    rebalanced_bill_changes_0_to_1[consumer0.archetype] = (
        consumer1.combined_fuel_bill - consumer0.combined_fuel_bill
    )

# %%
# Prepare data to plot
archetypes = [consumer.archetype for consumer in price_cap_0_consumers]
sq_change = [bill_changes_0_to_1[archetype] for archetype in archetypes]
rebalance_effect = [
    rebalanced_bill_changes_0_to_1[archetype] - bill_changes_0_to_1[archetype]
    for archetype in archetypes
]
sum_values = [neg + pos for neg, pos in zip(sq_change, rebalance_effect)]

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 5))

# Plot bars positive bars start from zero)

# Compute the bottom positions (only stack if effect of rebalancing is negative)
bottom_values = [sq if re < 0 else 0 for sq, re in zip(sq_change, rebalance_effect)]

ax.bar(
    archetypes,
    sq_change,
    color="#99CCFF",
    label="Bill change due to price cap change",
)
ax.bar(
    archetypes,
    rebalance_effect,
    color="#FF9999",
    label="Effect of rebalancing",
    bottom=bottom_values,  # Stack only when rebalance_effect is negative
)

# Plot dots at net effect positions
ax.scatter(archetypes, sum_values, color="#555555", zorder=3, label="Net bill change")

# Styling
ax.set_ylabel("Change in annual energy bill between price cap periods")
ax.set_title("Change in bill from (Jul-Sep 2023) to (Oct-Dec 2023)")
ax.grid(True, linestyle="--", alpha=0.7)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# #### **Price cap period n = 2: January - March 2024**

# %% [markdown]
# **1. Bill change with respect to the status quo bill**

# %%
price_cap_2_change_wrt_sq = {}

for consumer_sq, consumer_rb in zip(
    price_cap_2_consumers, rebalanced_price_cap_2_consumers
):
    price_cap_2_change_wrt_sq[consumer_sq.archetype] = (
        consumer_rb.combined_fuel_bill - consumer_sq.combined_fuel_bill
    )

# %%
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    list(price_cap_2_change_wrt_sq.keys()),
    list(price_cap_2_change_wrt_sq.values()),
    color="#FF9999",
)

# Styling
ax.set_ylabel("Difference in annual energy bill with respect to status quo")
ax.set_xlabel("Archetype")
ax.set_title(
    "Effect of rebalancing (FiT to gas) on annual energy bill in (Jan-Mar 2024)"
)
ax.grid(True, linestyle="--", alpha=0.7)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# Note that this is the same as the equivalent plot in Oct-Dec 2023 because no new rebalancing has been introduced.

# %% [markdown]
# **2. Bill change with respect to the bill under previous price cap**

# %%
# Under no rebalancing
bill_changes_1_to_2 = {}
for consumer1, consumer2 in zip(price_cap_1_consumers, price_cap_2_consumers):
    bill_changes_1_to_2[consumer1.archetype] = (
        consumer2.combined_fuel_bill - consumer1.combined_fuel_bill
    )

# %%
# With partial rebalancing
rebalanced_bill_changes_1_to_2 = {}
for consumer1, consumer2 in zip(
    rebalanced_price_cap_1_consumers, rebalanced_price_cap_2_consumers
):
    rebalanced_bill_changes_1_to_2[consumer1.archetype] = (
        consumer2.combined_fuel_bill - consumer1.combined_fuel_bill
    )

# %% [markdown]
# Plotting the effect of rebalancing

# %%
# Prepare data to plot
archetypes = [consumer.archetype for consumer in price_cap_1_consumers]
sq_change = [bill_changes_1_to_2[archetype] for archetype in archetypes]
rebalance_effect = [
    rebalanced_bill_changes_1_to_2[archetype] - bill_changes_1_to_2[archetype]
    for archetype in archetypes
]
sum_values = [neg + pos for neg, pos in zip(sq_change, rebalance_effect)]

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 5))

# Plot bars positive bars start from zero)

# Compute the bottom positions (only stack if effect of rebalancing is negative)
bottom_values = [sq if re < 0 else 0 for sq, re in zip(sq_change, rebalance_effect)]

ax.bar(
    archetypes,
    sq_change,
    color="#99CCFF",
    label="Bill change due to price cap change",
)
ax.bar(
    archetypes,
    rebalance_effect,
    color="#FF9999",
    label="Effect of rebalancing",
    bottom=bottom_values,  # Stack only when rebalance_effect is negative
)

# Plot dots at net effect positions
ax.scatter(archetypes, sum_values, color="#555555", zorder=3, label="Net bill change")

# Styling
ax.set_ylabel("Change in annual energy bill between price cap periods")
ax.set_title("Change in bill from (Oct-Dec 2023) to (Jan-Mar 2024)")
ax.grid(True, linestyle="--", alpha=0.7)  # Dashed gridlines with slight transparency
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# #### **Price cap period n = 3: April - June 2024**

# %% [markdown]
# **1. Bill change with respect to the status quo bill**

# %%
price_cap_3_change_wrt_sq = {}

for consumer_sq, consumer_rb in zip(
    price_cap_3_consumers, rebalanced_price_cap_3_consumers
):
    price_cap_3_change_wrt_sq[consumer_sq.archetype] = (
        consumer_rb.combined_fuel_bill - consumer_sq.combined_fuel_bill
    )

# %%
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    list(price_cap_3_change_wrt_sq.keys()),
    list(price_cap_3_change_wrt_sq.values()),
    color="#FF9999",
)

# Styling
ax.set_ylabel("Difference in annual energy bill with respect to status quo")
ax.set_xlabel("Archetype")
ax.set_title(
    "Effect of rebalancing (FiT + 1/2 RO to gas) on annual energy bill in (Apr-Jun 2024)"
)
ax.grid(True, linestyle="--", alpha=0.7)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# **2. Bill change with respect to the bill under previous price cap**

# %%
# Under no rebalancing
bill_changes_2_to_3 = {}
for consumer2, consumer3 in zip(price_cap_2_consumers, price_cap_3_consumers):
    bill_changes_2_to_3[consumer2.archetype] = (
        consumer3.combined_fuel_bill - consumer2.combined_fuel_bill
    )

# %%
# With partial rebalancing
rebalanced_bill_changes_2_to_3 = {}
for consumer2, consumer3 in zip(
    rebalanced_price_cap_2_consumers, rebalanced_price_cap_3_consumers
):
    rebalanced_bill_changes_2_to_3[consumer2.archetype] = (
        consumer3.combined_fuel_bill - consumer2.combined_fuel_bill
    )

# %%
# Prepare data to plot
archetypes = [consumer.archetype for consumer in price_cap_3_consumers]
sq_change = [bill_changes_2_to_3[archetype] for archetype in archetypes]
rebalance_effect = [
    rebalanced_bill_changes_2_to_3[archetype] - bill_changes_2_to_3[archetype]
    for archetype in archetypes
]
sum_values = [neg + pos for neg, pos in zip(sq_change, rebalance_effect)]

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 5))

# Plot bars positive bars start from zero)

# Compute the bottom positions (only stack if effect of rebalancing is negative)
bottom_values = [sq if re < 0 else 0 for sq, re in zip(sq_change, rebalance_effect)]

ax.bar(
    archetypes,
    sq_change,
    color="#99CCFF",
    label="Bill change due to price cap change",
    # bottom=bottom_values,
)
ax.bar(
    archetypes,
    rebalance_effect,
    color="#FF9999",
    label="Effect of rebalancing",
    bottom=bottom_values,  # Stack only when rebalance_effect is negative
)

# Plot dots at net effect positions
ax.scatter(archetypes, sum_values, color="#555555", zorder=3, label="Net bill change")

# Styling
ax.set_ylabel("Change in annual energy bill between price cap periods")
ax.set_title("Change in bill from (Jan-Mar 2024) to (Apr-Jun 2024)")
ax.grid(True, linestyle="--", alpha=0.7)  # Dashed gridlines with slight transparency
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# #### **Price cap period n = 4: July - September 2024**

# %% [markdown]
# **1. Bill change with respect to the status quo bill**

# %%
price_cap_4_change_wrt_sq = {}

for consumer_sq, consumer_rb in zip(
    price_cap_4_consumers, rebalanced_price_cap_4_consumers
):
    price_cap_4_change_wrt_sq[consumer_sq.archetype] = (
        consumer_rb.combined_fuel_bill - consumer_sq.combined_fuel_bill
    )

# %%
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(
    list(price_cap_4_change_wrt_sq.keys()),
    list(price_cap_4_change_wrt_sq.values()),
    color="#FF9999",
)

# Styling
ax.set_ylabel("Difference in annual energy bill with respect to status quo")
ax.set_xlabel("Archetype")
ax.set_title(
    "Effect of rebalancing (FiT + RO to gas) on annual energy bill in (Jul-Sep 2024)"
)
ax.grid(True, linestyle="--", alpha=0.7)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# **2. Bill change with respect to the bill under previous price cap**

# %%
# Under no rebalancing
bill_changes_3_to_4 = {}
for consumer3, consumer4 in zip(price_cap_3_consumers, price_cap_4_consumers):
    bill_changes_3_to_4[consumer3.archetype] = (
        consumer4.combined_fuel_bill - consumer3.combined_fuel_bill
    )

# %%
# With partial rebalancing
rebalanced_bill_changes_3_to_4 = {}
for consumer3, consumer4 in zip(
    rebalanced_price_cap_3_consumers, rebalanced_price_cap_4_consumers
):
    rebalanced_bill_changes_3_to_4[consumer3.archetype] = (
        consumer4.combined_fuel_bill - consumer3.combined_fuel_bill
    )

# %%
# Prepare data to plot
archetypes = [consumer.archetype for consumer in price_cap_0_consumers]
sq_change = [bill_changes_3_to_4[archetype] for archetype in archetypes]
rebalance_effect = [
    rebalanced_bill_changes_3_to_4[archetype] - bill_changes_3_to_4[archetype]
    for archetype in archetypes
]
sum_values = [neg + pos for neg, pos in zip(sq_change, rebalance_effect)]

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 5))

# Plot bars positive bars start from zero)

# Compute the bottom positions (only stack if effect of rebalancing is negative)
bottom_values = [sq if re < 0 else 0 for sq, re in zip(sq_change, rebalance_effect)]

ax.bar(
    archetypes,
    sq_change,
    color="#99CCFF",
    label="Bill change due to price cap change",
    # bottom=bottom_values,
)
ax.bar(
    archetypes,
    rebalance_effect,
    color="#FF9999",
    label="Effect of rebalancing",
    bottom=bottom_values,  # Stack only when rebalance_effect is negative
)

# Plot dots at net effect positions
ax.scatter(archetypes, sum_values, color="#555555", zorder=3, label="Net bill change")

# Styling
ax.set_ylabel("Change in annual energy bill between price cap periods")
ax.set_title("Change in bill from (Apr-Jun 2024) to (Jul-Sep 2024)")
ax.grid(True, linestyle="--", alpha=0.7)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3)
ax.set_xticklabels(archetypes, rotation=45)

plt.show()

# %% [markdown]
# ### Saving raw results to file

# %%
price_caps_lookup = {
    price_cap_0: "July - September 2023",
    price_cap_1: "October - December 2023",
    price_cap_2: "January - March 2024",
    price_cap_3: "April - June 2024",
    price_cap_4: "July - September 2024",
}


# %%
# Helper function
def make_dataframe_summary(
    sq_consumers, rebalanced_consumers, rebalanced_scenario_name, price_cap
) -> pd.DataFrame:
    price_cap_df = pd.concat(
        [
            sq_consumers.tidy_summary_consumers(scenario_name="Status quo"),
            rebalanced_consumers.tidy_summary_consumers(
                scenario_name=rebalanced_scenario_name
            ),
        ]
    )
    price_cap_df["PriceCapPeriod"] = price_caps_lookup.get(price_cap)
    return price_cap_df


# %%
# Price cap 0
price_cap_0_df = make_dataframe_summary(
    price_cap_0_consumers,
    price_cap_0_consumers,
    "Rebalanced",
    price_cap_0,
)

# %%
# Price cap 1
price_cap_1_df = make_dataframe_summary(
    price_cap_1_consumers,
    rebalanced_price_cap_1_consumers,
    "Rebalanced",
    price_cap_1,
)

# %%
# Price cap 2
price_cap_2_df = make_dataframe_summary(
    price_cap_2_consumers,
    rebalanced_price_cap_2_consumers,
    "Rebalanced",
    price_cap_2,
)

# %%
# Price cap 3
price_cap_3_df = make_dataframe_summary(
    price_cap_3_consumers,
    rebalanced_price_cap_3_consumers,
    "Rebalanced",
    price_cap_3,
)

# %%
# Price cap 4
price_cap_4_df = make_dataframe_summary(
    price_cap_4_consumers,
    rebalanced_price_cap_4_consumers,
    "Rebalanced",
    price_cap_4,
)

# %%
price_caps_df = pd.concat(
    [price_cap_0_df, price_cap_1_df, price_cap_2_df, price_cap_3_df, price_cap_4_df]
)

# %%
summary_df = price_caps_df.pivot_table(
    index=["Name", "Eligible for support", "PriceCapPeriod", "Scenario"],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()

summary_df = summary_df[
    [
        "Name",
        "Eligible for support",
        "main_heating_fuel",
        "PriceCapPeriod",
        "Scenario",
        "combined_fuel_bill",
    ]
]

# %%
# Add column for period index number
period_lookup = {
    "July - September 2023": 0,
    "October - December 2023": 1,
    "January - March 2024": 2,
    "April - June 2024": 3,
    "July - September 2024": 4,
}
summary_df["Period number"] = summary_df["PriceCapPeriod"].apply(
    lambda x: period_lookup.get(x)
)
summary_df["Period number"] = summary_df["Period number"].astype(int)

# %%
# Group sizes
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()

# Warm Home Discount sizes

# Core target recipients change each price cap period because revenue changes
whd_industry_initiatives = 50_000_000
whd_core_target_recipients = {
    price_caps_lookup.get(price_cap_0): (
        price_cap_0_pc["whd"].revenue - whd_industry_initiatives
    )
    / 150,
    price_caps_lookup.get(price_cap_1): (
        price_cap_1_pc["whd"].revenue - whd_industry_initiatives
    )
    / 150,
    price_caps_lookup.get(price_cap_2): (
        price_cap_2_pc["whd"].revenue - whd_industry_initiatives
    )
    / 150,
    price_caps_lookup.get(price_cap_3): (
        price_cap_3_pc["whd"].revenue - whd_industry_initiatives
    )
    / 150,
    price_caps_lookup.get(price_cap_4): (
        price_cap_4_pc["whd"].revenue - whd_industry_initiatives
    )
    / 150,
}

total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()
whd_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="WHDEligibleSize",
)

# Scale eligible group sizes down to WHD core target recipients
scaled_whd_sizes = {}
for price_cap, recipient_size in whd_core_target_recipients.items():
    scaling_factor = recipient_size / total_whd_group
    scaling_factor_remainder = 1 - scaling_factor
    scaled_whd_sizes[price_cap] = {
        k: {
            True: (v[True] * scaling_factor),
            False: v[False] + (v[True] * scaling_factor_remainder),
        }
        for k, v in whd_sizes.items()
    }

# Cold Weather Payment sizes
cwp_sizes_constant = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="CWPEligibleSize",
)
cwp_sizes = {}
for price_cap in whd_core_target_recipients.keys():
    cwp_sizes[price_cap] = cwp_sizes_constant

# Group size look-up
eligibility_size_lookup = {"WHD": scaled_whd_sizes, "CWP": cwp_sizes}

# Add eligibility group type column
summary_df["Eligibility"] = summary_df.apply(
    lambda row: (
        "WHD"
        if row["Scenario"] == "Status quo"
        else (
            "WHD"
            if row["Scenario"] == "Rebalanced" and row["Period number"] == 0
            else "CWP"
        )
    ),
    axis=1,
)

# Rename columns for easier processing
summary_df = summary_df.rename(columns={"Eligible for support": "EligibleForSupport"})

# %%
# Add group size value based on eligibility group and price cap period
group_sizes = []
for row in summary_df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.PriceCapPeriod)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
summary_df.loc[:, "GroupSize"] = group_sizes

# %%
# Add column for change in bill with respect to previous price cap period
summary_df = summary_df.sort_values(
    by=["Name", "EligibleForSupport", "Scenario", "Period number"]
)

summary_df["Bill change from previous price cap period"] = summary_df.groupby(
    ["Name", "EligibleForSupport", "Scenario"]
)["combined_fuel_bill"].diff()

# %% [markdown]
# Grouped results: Bill value

# %%
# Minimum, maximum and weighted averages for
# (i) gas-using households, eligible for support,
# (ii) gas-using households, ineligible for support,
# (iii) all others

# Create new Grouping column
summary_df["Grouping"] = summary_df.apply(
    lambda row: (
        "Eligible gas"
        if row["EligibleForSupport"] and row["main_heating_fuel"] == "Gas"
        else (
            "Ineligible gas"
            if not row["EligibleForSupport"] and row["main_heating_fuel"] == "Gas"
            else "All other"
        )
    ),
    axis=1,
)

# %%
# Get minimum, maximum and weighted average bill value for each scenario, period number and grouping
bill_agg_df = (
    summary_df.groupby(["Scenario", "Period number", "PriceCapPeriod", "Grouping"])
    .agg(
        Minimum=("combined_fuel_bill", "min"),
        Maximum=("combined_fuel_bill", "max"),
        Weighted_Average=(
            "combined_fuel_bill",
            lambda x: (x * summary_df.loc[x.index, "GroupSize"]).sum()
            / summary_df.loc[x.index, "GroupSize"].sum(),
        ),
    )
    .reset_index()
)

# Reshape
grouped_bill_summary_df = bill_agg_df.melt(
    id_vars=["Scenario", "Period number", "PriceCapPeriod", "Grouping"],
    var_name="Statistic",
    value_name="Annual energy bill",
)

# Rename columns for clarity
grouped_bill_summary_df.rename(
    columns={"PriceCapPeriod": "Price cap period"}, inplace=True
)

# %% [markdown]
# Grouped results: Bill change from previous price cap period

# %% [markdown]
# I think this is redundant, we can just use the weighted average bill values and use the changes of those.

# %%
# # Get minimum, maximum and weighted average bill change for each scenario, period number and grouping
# change_agg_df = (
#     summary_df.groupby(["Scenario", "Period number", "PriceCapPeriod", "Grouping"])
#     .agg(
#         Minimum=("Bill change from previous price cap period", "min"),
#         Maximum=("Bill change from previous price cap period", "max"),
#         Weighted_Average=(
#             "Bill change from previous price cap period",
#             lambda x: (x * summary_df.loc[x.index, "GroupSize"]).sum()
#             / summary_df.loc[x.index, "GroupSize"].sum(),
#         ),
#     )
#     .reset_index()
# )

# # Reshape
# grouped_change_summary_df = change_agg_df.melt(
#     id_vars=["Scenario", "Period number", "PriceCapPeriod", "Grouping"],
#     var_name="Statistic",
#     value_name="Bill change from previous price cap period",
# )

# # Rename columns for clarity
# grouped_change_summary_df.rename(
#     columns={"PriceCapPeriod": "Price cap period"}, inplace=True
# )

# %%
# Saving to Excel
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phasing_results.xlsx"

try:
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        # Write each DataFrame to a different sheet
        summary_df.to_excel(writer, sheet_name="Archetype bills", index=False)
        grouped_bill_summary_df.to_excel(
            writer, sheet_name="Grouped bills", index=False
        )
        # grouped_change_summary_df.to_excel(
        #     writer, sheet_name="Grouped bill changes", index=False
        # )

    print("Raw results data successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")
