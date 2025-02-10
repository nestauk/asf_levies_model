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

# %%
import pandas as pd
from datetime import datetime
from asf_levies_model.getters.load_data import (
    download_annex_4,
    download_annex_9,
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
    process_tariff_elec_other_payment_nil,
    process_tariff_elec_other_payment_typical,
    process_tariff_gas_other_payment_nil,
    process_tariff_gas_other_payment_typical,
    ofgem_archetypes_data,
    ofgem_archetypes_retired_pension,
    ofgem_archetypes_scheme_eligibility,
    ofgem_archetypes_benefit_recipients,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT, LevyCollection

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model import config, PROJECT_DIR

from asf_levies_model.consumers import Consumer, ConsumerCollection

from asf_levies_model.utils.utils import create_eligibility_group_sizes_dictionary

# %% [markdown]
# **Setting up Levy and Tariff objects**

# %%
# Denominator values from Desnz subnational consumption domestic data
supply_elec = 94_200_366
supply_gas = 265_197_947
customers_gas = 24_503_683
customers_elec = 29_078_770

denominator_values = {
    "supply_elec": supply_elec,
    "supply_gas": supply_gas,
    "customers_gas": customers_gas,
    "customers_elec": customers_elec,
}
denominators = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}

# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %%
# Initialise levies
fileobject = download_annex_4(as_fileobject=True)
levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=supply_elec),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=supply_elec),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=customers_gas),
    WHD.from_dataframe(
        process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
    ),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(
        process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
]
fileobject.close()
pc = LevyCollection("Policy Costs", "pc", levies, denominator_values)

# %%
# Initialise tariffs (Other Payment method)
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
print(f"From Ofgem: {pc.calculate_levies(2.7, 11.5, True, True)}")
pc.rebalance_to_denominators(inplace=True)
print(f"Rebalanced with our denominators: {pc.calculate_levies(2.7, 11.5, True, True)}")

# %%
# Gas tariff
gas_tariff = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# Electricity tariff
electricity_tariff = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

# %%
# Update baseline bill policy costs to match denominator adjusted policy costs
gas_tariff.update_policy_costs(pc, inplace=True)
electricity_tariff.update_policy_costs(pc, inplace=True)

# %% [markdown]
# **Setting up ConsumerCollection**

# %%
# Load archetypes headline data
ofgem_archetypes_df = ofgem_archetypes_data()

# %%
all_consumers = ConsumerCollection.from_dataframe(
    collection_name="All archetypes with eligibility",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# %% [markdown]
# Apply flat rebate of £150 to eligible consumers.

# %%
all_consumers_with_support = all_consumers.apply_support_to_eligible_consumers(
    "electricity", -150, "flat adjustment", inplace=False
)

# %%
# Verify discount has been applied to A1 eligible
(
    all_consumers.consumers[0].combined_fuel_bill
    - all_consumers_with_support.consumers[0].combined_fuel_bill
), all_consumers.consumers[0].name, all_consumers.consumers[0].scheme_eligible,

# %%
# Verify discount has NOT been applied to A1 ineligible
(
    all_consumers.consumers[24].combined_fuel_bill
    - all_consumers_with_support.consumers[24].combined_fuel_bill
), all_consumers.consumers[24].name, all_consumers.consumers[24].scheme_eligible,

# %% [markdown]
# Get tidy summary tables

# %%
baseline_df = all_consumers.tidy_summary_consumers(scenario_name="No support")
support_df = all_consumers_with_support.tidy_summary_consumers(
    scenario_name="£150 rebate"
)
master_df = pd.concat([baseline_df, support_df]).reset_index(drop=True)

# %%
master_df

# %% [markdown]
# Add eligibility and ineligibility group sizes

# %%
# Load scheme eligibility size data
ofgem_archetypes_scheme_eligibility_df = ofgem_archetypes_scheme_eligibility()

# Load pensioners size data
ofgem_archetypes_retired_pension_df = ofgem_archetypes_retired_pension()

# Load benefit recipients size data
ofgem_archetypes_benefit_recipients_df = ofgem_archetypes_benefit_recipients()

# %% [markdown]
# Let's assign the group sizes for Child Benefit recipients

# %%
# Check default group sizes
all_consumers.group_sizes

# %%
# Create a copy of the generic ConsumerCollection
consumers_with_child_benefit_eligibility = all_consumers.deepcopy()

# %%
# Create group_sizes dictionary with ChildBenefitRecipient size for eligible and ineligible groups
cbr_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_benefit_recipients_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="ChildBenefitRecipientSize",
)

# %%
print(cbr_sizes)

# %%
consumers_with_child_benefit_eligibility.group_sizes = cbr_sizes

# %%
# If we want the ineligible size for B4
consumers_with_child_benefit_eligibility.group_sizes.get("B4").get(False)

# %%
ofgem_archetypes_benefit_recipients_df
