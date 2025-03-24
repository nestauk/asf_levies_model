"""

Phase 2, Set 5 scenarios

All scenarios have:
- Rebalancing RO + FiT to gas
- Eligibility group is Cold Weather Payments
This set-up will be referred to as "Base".

Unlike Set 4, each scenario in this set has a different unit discount value.
Discount values were identified through an iterative process using (notebooks/phase_2_scenarios_unit_discount_finetuning.ipynb)
where the objective was to find the lowest discount value that leads to a bill saving for all gas-using households eligible for support.
Discount values were identified to the nearest 1 £/MWh.

Scenarios (name of corresponding ConsumerCollection):
00. Status quo (status_quo_consumers_flat_rebate)
0. Rebalancing only with no changes to WHD (rebalanced_consumers_flat_rebate)
-- Option 1 --
1. Base with original unit discount (scenario_1_consumers_unit_discount) <- Same as in Set 4
2. Base (scenario_2_consumers_unit_discount)
3. Base + Remove GBIS to general taxation (scenario_3_consumers_unit_discount)
4. Base + Remove GBIS + 1/3 ECO4 to general taxation (scenario_4_consumers_unit_discount)
5. Base + Remove ECO (ECO4+GBIS) to general taxation (scenario_5_consumers_unit_discountt)
-- Option 2 --
6. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation (scenario_6_consumers_unit_discount) <- Same as in Set 4
7. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation (scenario_7_consumers_unit_discount)
8. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation
   + Remove GBIS (scenario_8_consumers_unit_discount)
9. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation
   + Remove GBIS
   + Remove 1/3 ECO4 (scenario_9_consumers_unit_discount)
10. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation
   + Remove GBIS
   + Remove ECO4 (scenario_10_consumers_unit_discount)
-- Option 3, original --
11. Base + Remove ECO (ECO4+GBIS) to general taxation (scenario_11_consumers_unit_discount) <- Same as in Set 4
-- New as of 24-03-2025 --
12. Base + WHD levy revenue allocation on general taxation + Remove GBIS

"""

import pandas as pd
from datetime import datetime
import copy
import numpy as np

import asf_levies_model.levies as levies
import asf_levies_model.tariffs as tariffs
from asf_levies_model.consumers import Consumer, ConsumerCollection
import asf_levies_model.getters.load_data as data
from asf_levies_model.summary import create_scenario_weights_dict
from asf_levies_model.utils.utils import create_eligibility_group_sizes_dictionary
from asf_levies_model import PROJECT_DIR


"""
Setting up Levies and LevyCollection
"""

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

# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    249_044_438  # DESNZ GB total electricity consumption - all meters (2023)
)
exempt_eii_supply = 10_529_633  # Apr-Jun2025 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Scaling factor for estimating domestic share of NCC revenue
ncc_eligible_supply = 119_380_310.7  # Mar-Jun2025 period, Annex 4, NCC methodology tab
ncc_scaling_factor = supply_elec / ncc_eligible_supply

# Instantiate LevyCollection
fileobject = data.download_annex_4(as_fileobject=True)
list_levies = [
    levies.RO.from_dataframe(data.process_data_RO(fileobject), denominator=supply_elec),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject), denominator=supply_elec
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject), denominator=customers_gas
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
    ),
    levies.ECO4.from_dataframe(data.process_data_ECO(fileobject)),  # Split ECO
    levies.GBIS.from_dataframe(data.process_data_ECO(fileobject)),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
    levies.NCC.from_dataframe(
        data.process_data_NCC(fileobject), scaling_factor=ncc_scaling_factor
    ),
]
fileobject.close()
pc = levies.LevyCollection("Policy Costs", "pc", list_levies, denominator_values)

# Rebalance to denominators
pc = pc.rebalance_to_denominators()

"""
Setting up Tariffs
"""

# Instantiate Tariffs
fileobject = data.download_annex_9(as_fileobject=True)
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
)
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
)
fileobject.close()

# Update policy costs with denominator rebalanced policy costs
gas_tariff = gas_tariff.update_policy_costs(pc)
electricity_tariff = electricity_tariff.update_policy_costs(pc)


"""
00. Status quo
"""
# Create a status quo WHD rebate ConsumerCollection

ofgem_archetypes_df = data.ofgem_archetypes_data()

status_quo_consumers = ConsumerCollection.from_dataframe(
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
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

status_quo_consumers_flat_rebate = (
    status_quo_consumers.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)

"""
0. Rebalancing only with no changes to WHD
"""

# Create rebalancing weights for RO and FiT
rebalancing_weights = create_scenario_weights_dict(pc)
for levy in pc[["ro", "fit"]]:
    rebalancing_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# Apply rebalancing to RO and FiT in LevyCollection
rebalanced_pc = pc.rebalance_levies(
    rebalancing_weights, scenario_name="rebalance_ro_fit_to_gas"
)

# Update tariffs
rebalanced_gas_tariff = gas_tariff.update_policy_costs(rebalanced_pc)
rebalanced_electricity_tariff = electricity_tariff.update_policy_costs(rebalanced_pc)

# Create a rebalanced with status quo WHD rebate ConsumerCollection
rebalanced_consumers = ConsumerCollection.from_dataframe(
    collection_name="Baseline RO FiT on gas, WHD x 1",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=rebalanced_gas_tariff,
    electricity_tariff=rebalanced_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Apply status quo £150 WHD rebate
rebalanced_consumers_flat_rebate = (
    rebalanced_consumers.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)


"""
Defining WHD revenue parameters
"""
whd_industry_initiatives = 50_000_000
whd_core_target_recipients = (pc["whd"].revenue - whd_industry_initiatives) / 150

"""
Eligibility sizes
"""
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
total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()
whd_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="WHDEligibleSize",
)
# Scale eligible group sizes down to WHD core target recipients
scaling_factor = whd_core_target_recipients / total_whd_group
scaling_factor_remainder = 1 - scaling_factor
scaled_whd_sizes = {
    k: {
        True: (v[True] * scaling_factor),
        False: v[False] + (v[True] * scaling_factor_remainder),
    }
    for k, v in whd_sizes.items()
}

"""
CWP discount parameters
"""
# Estimate total electricity and gas consumption of all eligible households across archetypes
cwp_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers.iter_eligible()
)
cwp_recipients_gas_consumption = sum(
    consumer.gas_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers.iter_eligible()
)

"""
1. Base with original unit discount
"""

# Calculating unit discount based on target core spend
scenario_1_new_whd_core = 1_600_000_000

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
cwp_core_target_spending_electricity_weight = cwp_recipients_electricity_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)
cwp_core_target_spending_gas_weight = cwp_recipients_gas_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)

# Allocate spending to electricity and gas discount
scenario_1_core_target_spending_electricity = (
    scenario_1_new_whd_core * cwp_core_target_spending_electricity_weight
)
scenario_1_core_target_spending_gas = (
    scenario_1_new_whd_core * cwp_core_target_spending_gas_weight
)

# Calculate unit discounts for electricity and gas
scenario_1_unit_discount_electricity = (
    scenario_1_core_target_spending_electricity / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
scenario_1_unit_discount_gas = (
    scenario_1_core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# Update revenue
scenario_1_pc = rebalanced_pc.update_revenues(
    {"whd": (scenario_1_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_1_gas_tariff = gas_tariff.update_policy_costs(scenario_1_pc)
scenario_1_electricity_tariff = electricity_tariff.update_policy_costs(scenario_1_pc)

# Create ConsumerCollection
scenario_1_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 1",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_1_gas_tariff,
    electricity_tariff=scenario_1_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_1_consumers_unit_discount = (
    scenario_1_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_1_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_1_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
2. Base with lower unit discount
"""

# Define unit discounts
scenario_2_unit_discount_electricity = 19  # £/MWh, inclusive of VAT
scenario_2_unit_discount_gas = 19  # £/MWh, inclusive of VAT

# Calculate spending
scenario_2_core_target_spending_electricity = (
    scenario_2_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_2_core_target_spending_gas = (
    scenario_2_unit_discount_electricity / 1.05
) * cwp_recipients_gas_consumption
scenario_2_new_whd_core = (
    scenario_2_core_target_spending_electricity + scenario_2_core_target_spending_gas
)

# Update revenue
scenario_2_pc = rebalanced_pc.update_revenues(
    {"whd": (scenario_2_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_2_gas_tariff = gas_tariff.update_policy_costs(scenario_2_pc)
scenario_2_electricity_tariff = electricity_tariff.update_policy_costs(scenario_2_pc)

# Create ConsumerCollection
scenario_2_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 1 with alternative unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_2_gas_tariff,
    electricity_tariff=scenario_2_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_2_consumers_unit_discount = (
    scenario_2_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_2_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_2_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
3. Base + Remove GBIS to general taxation, with lower unit discount
"""

# Define unit discounts
scenario_3_unit_discount_electricity = 17  # £/MWh, inclusive of VAT
scenario_3_unit_discount_gas = 17  # £/MWh, inclusive of VAT

# Calculate spending
scenario_3_core_target_spending_electricity = (
    scenario_3_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_3_core_target_spending_gas = (
    scenario_3_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_3_new_whd_core = (
    scenario_3_core_target_spending_electricity + scenario_3_core_target_spending_gas
)

# Add rebalancing weights for GBIS removal
rebalancing_weights_delete_gbis = copy.deepcopy(rebalancing_weights)
rebalancing_weights_delete_gbis["gbis"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_3_pc = pc.rebalance_levies(
    rebalancing_weights_delete_gbis,
    scenario_name="rebalance_ro_fit_to_gas_gbis_to_tax",
)

# Update revenue
scenario_3_pc = scenario_3_pc.update_revenues(
    {"whd": (scenario_3_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_3_gas_tariff = gas_tariff.update_policy_costs(scenario_3_pc)
scenario_3_electricity_tariff = electricity_tariff.update_policy_costs(scenario_3_pc)

# Create ConsumerCollection
scenario_3_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 1 + remove GBIS, with alternative unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_3_gas_tariff,
    electricity_tariff=scenario_3_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_3_consumers_unit_discount = (
    scenario_3_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_3_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_3_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
4. Base + Remove GBIS + 1/3 ECO4 to general taxation, with lower unit discount
"""

# Define unit discounts
scenario_4_unit_discount_electricity = 15  # £/MWh, inclusive of VAT
scenario_4_unit_discount_gas = 15  # £/MWh, inclusive of VAT

# Calculate spending
scenario_4_core_target_spending_electricity = (
    scenario_4_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_4_core_target_spending_gas = (
    scenario_4_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_4_new_whd_core = (
    scenario_4_core_target_spending_electricity + scenario_4_core_target_spending_gas
)

# Add rebalancing weights for 1/3 ECO4 removal
rebalancing_weights_delete_gbis_third_eco = copy.deepcopy(
    rebalancing_weights_delete_gbis
)
rebalancing_weights_delete_gbis_third_eco["eco4"] = {
    "new_electricity_weight": 1 / 3,
    "new_gas_weight": 1 / 3,
    "new_tax_weight": 1 / 3,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_4_pc = pc.rebalance_levies(
    rebalancing_weights_delete_gbis_third_eco,
    scenario_name="rebalance_ro_fit_to_gas_gbis_to_tax_third_eco4_to_tax",
)

# Update revenue
scenario_4_pc = scenario_4_pc.update_revenues(
    {"whd": (scenario_4_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_4_gas_tariff = gas_tariff.update_policy_costs(scenario_4_pc)
scenario_4_electricity_tariff = electricity_tariff.update_policy_costs(scenario_4_pc)

# Create ConsumerCollection
scenario_4_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 1 + remove GBIS + remove 1/3 ECO4, with alternative unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_4_gas_tariff,
    electricity_tariff=scenario_4_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_4_consumers_unit_discount = (
    scenario_4_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_4_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_4_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
5. Base + Remove GBIS + ECO4 to general taxation, with lower unit discount
"""

# Define unit discounts
scenario_5_unit_discount_electricity = 13  # £/MWh, inclusive of VAT
scenario_5_unit_discount_gas = 13  # £/MWh, inclusive of VAT

# Calculate spending
scenario_5_core_target_spending_electricity = (
    scenario_5_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_5_core_target_spending_gas = (
    scenario_5_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_5_new_whd_core = (
    scenario_5_core_target_spending_electricity + scenario_5_core_target_spending_gas
)

# Add rebalancing weights for full ECO4 removal
rebalancing_weights_delete_eco = copy.deepcopy(rebalancing_weights_delete_gbis)
rebalancing_weights_delete_eco["eco4"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_5_pc = pc.rebalance_levies(
    rebalancing_weights_delete_eco,
    scenario_name="rebalance_ro_fit_to_gas_eco_to_tax",
)

# Update revenue
scenario_5_pc = scenario_5_pc.update_revenues(
    {"whd": (scenario_5_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_5_gas_tariff = gas_tariff.update_policy_costs(scenario_5_pc)
scenario_5_electricity_tariff = electricity_tariff.update_policy_costs(scenario_5_pc)

# Create ConsumerCollection
scenario_5_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 1 + remove GBIS + ECO4, with alternative unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_5_gas_tariff,
    electricity_tariff=scenario_5_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_5_consumers_unit_discount = (
    scenario_5_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_5_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_5_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
Option 2 rebalanced policy costs for scenarios 6 to 10
"""
# Calculate new revenue weights for gas and electricity, scale down current weights from 1 to 1/3
new_whd_gas_weight = pc["whd"].gas_weight * (1 / 2)
new_whd_elec_weight = (1 / 2) - new_whd_gas_weight

# Add rebalancing weights for WHD to existing rebalancing dictionary for RO and FiT
rebalancing_weights_half_whd = copy.deepcopy(rebalancing_weights)
rebalancing_weights_half_whd["whd"] = {
    "new_electricity_weight": new_whd_elec_weight,
    "new_gas_weight": new_whd_gas_weight,
    "new_tax_weight": 1 / 2,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 1,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 1,
}

# Apply rebalancing weights
rebalanced_half_whd_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_half_to_tax",
)


"""
6. Base + Remove 1/2 WHD, with original unit discount
"""

# Calculating unit discount based on target core spend
scenario_6_new_whd_core = 1_600_000_000

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
cwp_core_target_spending_electricity_weight = cwp_recipients_electricity_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)
cwp_core_target_spending_gas_weight = cwp_recipients_gas_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)

# Allocate spending to electricity and gas discount
scenario_6_core_target_spending_electricity = (
    scenario_6_new_whd_core * cwp_core_target_spending_electricity_weight
)
scenario_6_core_target_spending_gas = (
    scenario_6_new_whd_core * cwp_core_target_spending_gas_weight
)

# Calculate unit discounts for electricity and gas
scenario_6_unit_discount_electricity = (
    scenario_6_core_target_spending_electricity / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
scenario_6_unit_discount_gas = (
    scenario_6_core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# Update revenue using rebalanced policy costs (RO+FiT to gas, 1/2 WHD to tax)
scenario_6_pc = rebalanced_half_whd_pc.update_revenues(
    {"whd": (scenario_6_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_6_gas_tariff = gas_tariff.update_policy_costs(scenario_6_pc)
scenario_6_electricity_tariff = electricity_tariff.update_policy_costs(scenario_6_pc)

# Create ConsumerCollection
scenario_6_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 2",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_6_gas_tariff,
    electricity_tariff=scenario_6_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_6_consumers_unit_discount = (
    scenario_6_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_6_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_6_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
7. Base + Remove 1/2 WHD, with lower unit discount
"""

# Define unit discounts
scenario_7_unit_discount_electricity = 16  # £/MWh, inclusive of VAT
scenario_7_unit_discount_gas = 16  # £/MWh, inclusive of VAT

# Calculate spending
scenario_7_core_target_spending_electricity = (
    scenario_7_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_7_core_target_spending_gas = (
    scenario_7_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_7_new_whd_core = (
    scenario_7_core_target_spending_electricity + scenario_7_core_target_spending_gas
)

# Update revenue using rebalanced policy costs (RO+FiT to gas, 1/2 WHD to tax)
scenario_7_pc = rebalanced_half_whd_pc.update_revenues(
    {"whd": (scenario_7_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_7_gas_tariff = gas_tariff.update_policy_costs(scenario_7_pc)
scenario_7_electricity_tariff = electricity_tariff.update_policy_costs(scenario_7_pc)

# Create ConsumerCollection
scenario_7_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 2 with lower unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_7_gas_tariff,
    electricity_tariff=scenario_7_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_7_consumers_unit_discount = (
    scenario_7_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_7_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_7_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
8. Base + Remove 1/2 WHD + Remove GBIS, with lower unit discount
"""

# Define unit discounts
scenario_8_unit_discount_electricity = 15  # £/MWh, inclusive of VAT
scenario_8_unit_discount_gas = 15  # £/MWh, inclusive of VAT

# Calculate spending
scenario_8_core_target_spending_electricity = (
    scenario_8_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_8_core_target_spending_gas = (
    scenario_8_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_8_new_whd_core = (
    scenario_8_core_target_spending_electricity + scenario_8_core_target_spending_gas
)

# Add rebalancing weights for GBIS removal
rebalancing_weights_half_whd_delete_gbis = copy.deepcopy(rebalancing_weights_half_whd)
rebalancing_weights_half_whd_delete_gbis["gbis"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_8_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_gbis,
    scenario_name="rebalance_ro_fit_to_gas_half_whd_to_tax_gbis_to_tax",
)

# Update revenue
scenario_8_pc = scenario_8_pc.update_revenues(
    {"whd": (scenario_8_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_8_gas_tariff = gas_tariff.update_policy_costs(scenario_8_pc)
scenario_8_electricity_tariff = electricity_tariff.update_policy_costs(scenario_8_pc)

# Create ConsumerCollection
scenario_8_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 2 + remove GBIS, with lower unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_8_gas_tariff,
    electricity_tariff=scenario_8_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_8_consumers_unit_discount = (
    scenario_8_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_8_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_8_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
9. Base + Remove 1/2 WHD + GBIS + 1/3 ECO4, with lower unit discount
"""

# Define unit discounts
scenario_9_unit_discount_electricity = 14  # £/MWh, inclusive of VAT
scenario_9_unit_discount_gas = 14  # £/MWh, inclusive of VAT

# Calculate spending
scenario_9_core_target_spending_electricity = (
    scenario_9_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_9_core_target_spending_gas = (
    scenario_9_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_9_new_whd_core = (
    scenario_9_core_target_spending_electricity + scenario_9_core_target_spending_gas
)

# Add rebalancing weights for 1/3 ECO4
rebalancing_weights_half_whd_delete_gbis_third_eco = copy.deepcopy(
    rebalancing_weights_half_whd_delete_gbis
)
rebalancing_weights_half_whd_delete_gbis_third_eco["eco4"] = {
    "new_electricity_weight": 1 / 3,
    "new_gas_weight": 1 / 3,
    "new_tax_weight": 1 / 3,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_9_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_gbis_third_eco,
    scenario_name="rebalance_ro_fit_to_gas_half_whd_to_tax_gbis_to_tax_third_eco4_to_tax",
)

# Update revenue
scenario_9_pc = scenario_9_pc.update_revenues(
    {"whd": (scenario_9_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_9_gas_tariff = gas_tariff.update_policy_costs(scenario_9_pc)
scenario_9_electricity_tariff = electricity_tariff.update_policy_costs(scenario_9_pc)

# Create ConsumerCollection
scenario_9_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 2 + remove GBIS + 1/3 ECO4, with lower unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_9_gas_tariff,
    electricity_tariff=scenario_9_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_9_consumers_unit_discount = (
    scenario_9_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_9_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_9_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
10. Base + Remove 1/2 WHD + GBIS + ECO4, with lower unit discount
"""

# Define unit discounts
scenario_10_unit_discount_electricity = 11  # £/MWh, inclusive of VAT
scenario_10_unit_discount_gas = 11  # £/MWh, inclusive of VAT

# Calculate spending
scenario_10_core_target_spending_electricity = (
    scenario_10_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_10_core_target_spending_gas = (
    scenario_10_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_10_new_whd_core = (
    scenario_10_core_target_spending_electricity + scenario_10_core_target_spending_gas
)

# Add rebalancing weights for 1/3 ECO4
rebalancing_weights_half_whd_delete_eco = copy.deepcopy(
    rebalancing_weights_half_whd_delete_gbis
)
rebalancing_weights_half_whd_delete_eco["eco4"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_10_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_eco,
    scenario_name="rebalance_ro_fit_to_gas_half_whd_to_tax_eco_to_tax",
)

# Update revenue
scenario_10_pc = scenario_10_pc.update_revenues(
    {"whd": (scenario_10_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_10_gas_tariff = gas_tariff.update_policy_costs(scenario_10_pc)
scenario_10_electricity_tariff = electricity_tariff.update_policy_costs(scenario_10_pc)

# Create ConsumerCollection
scenario_10_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 2 + remove GBIS + ECO4, with lower unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_10_gas_tariff,
    electricity_tariff=scenario_10_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_10_consumers_unit_discount = (
    scenario_10_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_10_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_10_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
11. Base + Remove ECO (GBIS+ECO4) with original unit discount
"""

# Calculating unit discount based on target core spend
scenario_11_new_whd_core = 1_600_000_000

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
cwp_core_target_spending_electricity_weight = cwp_recipients_electricity_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)
cwp_core_target_spending_gas_weight = cwp_recipients_gas_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)

# Allocate spending to electricity and gas discount
scenario_11_core_target_spending_electricity = (
    scenario_11_new_whd_core * cwp_core_target_spending_electricity_weight
)
scenario_11_core_target_spending_gas = (
    scenario_11_new_whd_core * cwp_core_target_spending_gas_weight
)

# Calculate unit discounts for electricity and gas
scenario_11_unit_discount_electricity = (
    scenario_11_core_target_spending_electricity
    / cwp_recipients_electricity_consumption
) * 1.05  # adding VAT to discount
scenario_11_unit_discount_gas = (
    scenario_11_core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# Apply rebalancing weights
scenario_11_pc = pc.rebalance_levies(
    rebalancing_weights_delete_eco,
    scenario_name="rebalance_ro_fit_to_gas_eco_to_tax",
)

# Update revenue using rebalanced policy costs
scenario_11_pc = scenario_11_pc.update_revenues(
    {"whd": (scenario_11_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_11_gas_tariff = gas_tariff.update_policy_costs(scenario_11_pc)
scenario_11_electricity_tariff = electricity_tariff.update_policy_costs(scenario_11_pc)

# Create ConsumerCollection
scenario_11_consumers = ConsumerCollection.from_dataframe(
    collection_name="Option 3",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_11_gas_tariff,
    electricity_tariff=scenario_11_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_11_consumers_unit_discount = (
    scenario_11_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_11_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_11_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
12. Base + Remove GBIS + WHD to general taxation, with lower unit discount
"""

# Define unit discounts
scenario_12_unit_discount_electricity = 13  # £/MWh, inclusive of VAT
scenario_12_unit_discount_gas = 13  # £/MWh, inclusive of VAT

# Calculate spending
scenario_12_core_target_spending_electricity = (
    scenario_12_unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
scenario_12_core_target_spending_gas = (
    scenario_12_unit_discount_gas / 1.05
) * cwp_recipients_gas_consumption
scenario_12_new_whd_core = (
    scenario_12_core_target_spending_electricity + scenario_12_core_target_spending_gas
)

# Add rebalancing weights for WHD removal to taxation
rebalancing_weights_delete_gbis_whd = copy.deepcopy(rebalancing_weights_delete_gbis)
rebalancing_weights_delete_gbis_whd["whd"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
scenario_12_pc = pc.rebalance_levies(
    rebalancing_weights_delete_gbis_whd,
    scenario_name="rebalance_ro_fit_to_gas_gbis_to_tax_whd_to_tax",
)

# Update revenue
scenario_12_pc = scenario_12_pc.update_revenues(
    {"whd": (scenario_12_new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
scenario_12_gas_tariff = gas_tariff.update_policy_costs(scenario_12_pc)
scenario_12_electricity_tariff = electricity_tariff.update_policy_costs(scenario_12_pc)

# Create ConsumerCollection
scenario_12_consumers = ConsumerCollection.from_dataframe(
    collection_name="Remove GBIS + WHD, with alternative unit discount",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=scenario_12_gas_tariff,
    electricity_tariff=scenario_12_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
scenario_12_consumers_unit_discount = (
    scenario_12_consumers.apply_support_to_eligible_consumers(
        "electricity",
        scenario_12_unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", scenario_12_unit_discount_gas, "unit discount", inplace=False
    )
)

"""
Printing outputs
"""

scenario_description = {
    "status quo": "Status quo",
    "rebalanced": "Rebalance RO+FiT to gas",
    "scenario_1": "CORE, original",
    "scenario_2": "CORE, alt",
    "scenario_3": "CORE + Remove GBIS",
    "scenario_4": "CORE + Remove GBIS + 1/3 ECO4",
    "scenario_5": "CORE + Remove GBIS + ECO4, alt",
    "scenario_6": "CORE + Remove 1/2 WHD, original",
    "scenario_7": "CORE + Remove 1/2 WHD, alt",
    "scenario_8": "CORE + Remove 1/2 WHD + GBIS",
    "scenario_9": "CORE + Remove 1/2 WHD + GBIS + 1/3 ECO4",
    "scenario_10": "CORE + Remove 1/2 WHD + GBIS + ECO4",
    "scenario_11": "CORE + Remove GBIS + ECO4, original",
    "scenario_12": "CORE + Remove WHD + GBIS",
}

# Information about levies
levy_collections = {
    pc: scenario_description.get("status quo"),
    rebalanced_pc: scenario_description.get("rebalanced"),
    scenario_1_pc: scenario_description.get("scenario_1"),
    scenario_2_pc: scenario_description.get("scenario_2"),
    scenario_3_pc: scenario_description.get("scenario_3"),
    scenario_4_pc: scenario_description.get("scenario_4"),
    scenario_5_pc: scenario_description.get("scenario_5"),
    scenario_6_pc: scenario_description.get("scenario_6"),
    scenario_7_pc: scenario_description.get("scenario_7"),
    scenario_8_pc: scenario_description.get("scenario_8"),
    scenario_9_pc: scenario_description.get("scenario_9"),
    scenario_10_pc: scenario_description.get("scenario_10"),
    scenario_11_pc: scenario_description.get("scenario_11"),
    scenario_12_pc: scenario_description.get("scenario_12"),
}


levies_info_df = pd.DataFrame()
for pc in levy_collections.keys():
    levies = [levy for levy in pc]
    levies.append(pc.union_levies())
    for levy in levies:
        row = pd.DataFrame(
            [
                {
                    "Scenario": levy_collections.get(pc),
                    "Levy": levy.name,
                    "Electricity standing charge (£/customer)": levy.electricity_fixed_rate,
                    "Electricity unit cost (£/MWh)": levy.electricity_variable_rate,
                    "Gas standing charge (£/customer)": levy.gas_fixed_rate,
                    "Gas unit cost (£/MWh)": levy.gas_variable_rate,
                    "Total revenue (£)": levy.revenue,
                    "Revenue proportion from electricity": levy.electricity_weight,
                    "Revenue proportion from gas": levy.gas_weight,
                    "Revenue proportion from tax": levy.tax_weight,
                }
            ]
        )
        levies_info_df = pd.concat([levies_info_df, row])
tidy_levies_info = pd.melt(levies_info_df, id_vars=["Scenario", "Levy"])

# Information about Tariffs
tariffs = {
    gas_tariff: scenario_description.get("status quo"),
    electricity_tariff: scenario_description.get("status quo"),
    rebalanced_gas_tariff: scenario_description.get("rebalanced"),
    rebalanced_electricity_tariff: scenario_description.get("rebalanced"),
    scenario_1_gas_tariff: scenario_description.get("scenario_1"),
    scenario_1_electricity_tariff: scenario_description.get("scenario_1"),
    scenario_2_gas_tariff: scenario_description.get("scenario_2"),
    scenario_2_electricity_tariff: scenario_description.get("scenario_2"),
    scenario_3_gas_tariff: scenario_description.get("scenario_3"),
    scenario_3_electricity_tariff: scenario_description.get("scenario_3"),
    scenario_4_gas_tariff: scenario_description.get("scenario_4"),
    scenario_4_electricity_tariff: scenario_description.get("scenario_4"),
    scenario_5_gas_tariff: scenario_description.get("scenario_5"),
    scenario_5_electricity_tariff: scenario_description.get("scenario_5"),
    scenario_6_gas_tariff: scenario_description.get("scenario_6"),
    scenario_6_electricity_tariff: scenario_description.get("scenario_6"),
    scenario_7_gas_tariff: scenario_description.get("scenario_7"),
    scenario_7_electricity_tariff: scenario_description.get("scenario_7"),
    scenario_8_gas_tariff: scenario_description.get("scenario_8"),
    scenario_8_electricity_tariff: scenario_description.get("scenario_8"),
    scenario_9_gas_tariff: scenario_description.get("scenario_9"),
    scenario_9_electricity_tariff: scenario_description.get("scenario_9"),
    scenario_10_gas_tariff: scenario_description.get("scenario_10"),
    scenario_10_electricity_tariff: scenario_description.get("scenario_10"),
    scenario_11_gas_tariff: scenario_description.get("scenario_11"),
    scenario_11_electricity_tariff: scenario_description.get("scenario_11"),
    scenario_12_gas_tariff: scenario_description.get("scenario_12"),
    scenario_12_electricity_tariff: scenario_description.get("scenario_12"),
}

tariffs_info_df = pd.DataFrame()
for tariff in tariffs.keys():
    row = pd.DataFrame(
        [
            {
                "Scenario": tariffs.get(tariff),
                "Tariff": tariff.name,
                "Fuel": tariff.fuel,
                "Nil consumption (£ per year)": tariff.calculate_nil_consumption(),
                "Variable consumption (£/MWh)": tariff.calculate_variable_consumption(
                    1
                ),
            }
        ]
    )
    tariffs_info_df = pd.concat([tariffs_info_df, row])
tidy_tariffs_info = pd.melt(tariffs_info_df, id_vars=["Scenario", "Tariff"])

# Information about electricity to gas unit price ratio
tariff_pairs = {
    (electricity_tariff, gas_tariff): scenario_description.get("status quo"),
    (rebalanced_electricity_tariff, rebalanced_gas_tariff): scenario_description.get(
        "rebalanced"
    ),
    (scenario_1_electricity_tariff, scenario_1_gas_tariff): scenario_description.get(
        "scenario_1"
    ),
    (scenario_2_electricity_tariff, scenario_2_gas_tariff): scenario_description.get(
        "scenario_2"
    ),
    (scenario_3_electricity_tariff, scenario_3_gas_tariff): scenario_description.get(
        "scenario_3"
    ),
    (scenario_4_electricity_tariff, scenario_4_gas_tariff): scenario_description.get(
        "scenario_4"
    ),
    (scenario_5_electricity_tariff, scenario_5_gas_tariff): scenario_description.get(
        "scenario_5"
    ),
    (scenario_6_electricity_tariff, scenario_6_gas_tariff): scenario_description.get(
        "scenario_6"
    ),
    (scenario_7_electricity_tariff, scenario_7_gas_tariff): scenario_description.get(
        "scenario_7"
    ),
    (scenario_8_electricity_tariff, scenario_8_gas_tariff): scenario_description.get(
        "scenario_8"
    ),
    (scenario_9_electricity_tariff, scenario_9_gas_tariff): scenario_description.get(
        "scenario_9"
    ),
    (scenario_10_electricity_tariff, scenario_10_gas_tariff): scenario_description.get(
        "scenario_10"
    ),
    (scenario_11_electricity_tariff, scenario_11_gas_tariff): scenario_description.get(
        "scenario_11"
    ),
    (scenario_12_electricity_tariff, scenario_12_gas_tariff): scenario_description.get(
        "scenario_12"
    ),
}

cost_ratio_df = pd.DataFrame()
for (tariff_electricity, tariff_gas), scenario in tariff_pairs.items():
    electricity_cost = tariff_electricity.calculate_variable_consumption(1)
    gas_cost = tariff_gas.calculate_variable_consumption(1)
    ratio = electricity_cost / gas_cost

    row = pd.DataFrame(
        [
            {
                "Scenario": scenario,
                "Electricity to gas unit cost ratio": ratio,
            }
        ]
    )
    cost_ratio_df = pd.concat([cost_ratio_df, row], ignore_index=True)


# Information about Consumers
consumer_collections_levy_scenario = {
    status_quo_consumers_flat_rebate: scenario_description.get("status quo"),
    rebalanced_consumers_flat_rebate: scenario_description.get("rebalanced"),
    scenario_1_consumers_unit_discount: scenario_description.get("scenario_1"),
    scenario_2_consumers_unit_discount: scenario_description.get("scenario_2"),
    scenario_3_consumers_unit_discount: scenario_description.get("scenario_3"),
    scenario_4_consumers_unit_discount: scenario_description.get("scenario_4"),
    scenario_5_consumers_unit_discount: scenario_description.get("scenario_5"),
    scenario_6_consumers_unit_discount: scenario_description.get("scenario_6"),
    scenario_7_consumers_unit_discount: scenario_description.get("scenario_7"),
    scenario_8_consumers_unit_discount: scenario_description.get("scenario_8"),
    scenario_9_consumers_unit_discount: scenario_description.get("scenario_9"),
    scenario_10_consumers_unit_discount: scenario_description.get("scenario_10"),
    scenario_11_consumers_unit_discount: scenario_description.get("scenario_11"),
    scenario_12_consumers_unit_discount: scenario_description.get("scenario_12"),
}

consumer_collections_support_type = {
    status_quo_consumers_flat_rebate: "Flat rebate",
    rebalanced_consumers_flat_rebate: "Flat rebate",
    scenario_1_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_2_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_3_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_4_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_5_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_6_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_7_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_8_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_9_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_10_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_11_consumers_unit_discount: "Unit discount on gas and electricity",
    scenario_12_consumers_unit_discount: "Unit discount on gas and electricity",
}

consumer_collections_eligibility = {
    status_quo_consumers_flat_rebate: "WHD",
    rebalanced_consumers_flat_rebate: "WHD",
    scenario_1_consumers_unit_discount: "CWP",
    scenario_2_consumers_unit_discount: "CWP",
    scenario_3_consumers_unit_discount: "CWP",
    scenario_4_consumers_unit_discount: "CWP",
    scenario_5_consumers_unit_discount: "CWP",
    scenario_6_consumers_unit_discount: "CWP",
    scenario_7_consumers_unit_discount: "CWP",
    scenario_8_consumers_unit_discount: "CWP",
    scenario_9_consumers_unit_discount: "CWP",
    scenario_10_consumers_unit_discount: "CWP",
    scenario_11_consumers_unit_discount: "CWP",
    scenario_12_consumers_unit_discount: "CWP",
}

tidy_consumers_info = pd.DataFrame()
for (
    consumers
) in (
    consumer_collections_levy_scenario.keys()
):  # update and add more information about scenarios
    df = consumers.tidy_summary_consumers(
        scenario_name=consumer_collections_levy_scenario.get(consumers)
    )
    df["Support type"] = consumer_collections_support_type.get(consumers)
    df["Eligibility"] = consumer_collections_eligibility.get(consumers)
    tidy_consumers_info = pd.concat([tidy_consumers_info, df])


# Support scenarios information
support_info_df = pd.DataFrame()

levies.append(pc.union_levies())

status_quo_row = pd.DataFrame(
    [
        {
            "Levy reform": "Status quo",
            "Targeted group": "WHD",
            "Public spend (£ per year)": pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": pc["whd"].revenue,
            "WHD target spend on support (£ per year)": pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": None,
            "WHD target spend on gas consumption of target households (£)": None,
            "Total electricity consumption of target households (MWh)": None,
            "Total gas consumption of target households (MWh)": None,
            "Flat rebate (£)": 150,
        }
    ]
)

rebalanced_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas",
            "Targeted group": "WHD",
            "Public spend (£ per year)": rebalanced_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": rebalanced_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": rebalanced_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": None,
            "WHD target spend on gas consumption of target households (£)": None,
            "Total electricity consumption of target households (MWh)": None,
            "Total gas consumption of target households (MWh)": None,
            "Flat rebate (£)": 150,
        }
    ]
)

scenario_1_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_1"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_1_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_1_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_1_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_1_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_1_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_1_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_1_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_1_unit_discount_electricity
                / scenario_1_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_1_unit_discount_gas
                / scenario_1_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_2_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_2"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_2_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_2_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_2_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_2_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_2_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_2_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_2_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_2_unit_discount_electricity
                / scenario_2_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_2_unit_discount_gas
                / scenario_2_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_3_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_3"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_3_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_3_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_3_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_3_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_3_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_3_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_3_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_3_unit_discount_electricity
                / scenario_3_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_3_unit_discount_gas
                / scenario_3_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_4_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_4"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_4_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_4_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_4_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_4_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_4_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_4_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_4_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_4_unit_discount_electricity
                / scenario_4_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_4_unit_discount_gas
                / scenario_4_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_5_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_5"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_5_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_5_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_5_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_5_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_5_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_5_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_5_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_5_unit_discount_electricity
                / scenario_5_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_5_unit_discount_gas
                / scenario_5_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_6_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_6"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_6_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_6_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_6_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_6_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_6_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_6_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_6_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_6_unit_discount_electricity
                / scenario_6_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_6_unit_discount_gas
                / scenario_6_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_7_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_7"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_7_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_7_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_7_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_7_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_7_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_7_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_7_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_7_unit_discount_electricity
                / scenario_7_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_7_unit_discount_gas
                / scenario_7_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_8_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_8"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_8_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_8_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_8_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_8_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_8_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_8_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_8_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_8_unit_discount_electricity
                / scenario_8_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_8_unit_discount_gas
                / scenario_8_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_9_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_9"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_9_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_9_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_9_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_9_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_9_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_9_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_9_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_9_unit_discount_electricity
                / scenario_9_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_9_unit_discount_gas
                / scenario_9_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_10_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_10"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_10_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_10_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_10_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_10_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_10_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_10_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_10_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_10_unit_discount_electricity
                / scenario_10_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_10_unit_discount_gas
                / scenario_10_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_11_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_11"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_11_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_11_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_11_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_11_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_11_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_11_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_11_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_11_unit_discount_electricity
                / scenario_11_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_11_unit_discount_gas
                / scenario_11_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

scenario_12_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("scenario_12"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": scenario_12_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": scenario_12_pc["whd"].revenue,
            "WHD target spend on support (£ per year)": scenario_12_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": scenario_12_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": scenario_12_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": scenario_12_unit_discount_electricity,
            "Unit discount gas (£/MWh)": scenario_12_unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                scenario_12_unit_discount_electricity
                / scenario_12_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                scenario_12_unit_discount_gas
                / scenario_12_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

support_info_df = pd.concat(
    [
        status_quo_row,
        rebalanced_row,
        scenario_1_row,
        scenario_2_row,
        scenario_3_row,
        scenario_4_row,
        scenario_5_row,
        scenario_6_row,
        scenario_7_row,
        scenario_8_row,
        scenario_9_row,
        scenario_10_row,
        scenario_11_row,
        scenario_12_row,
    ]
)

"""
Saving raw results data to Excel
"""
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_5.xlsx"

try:
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        # Write each DataFrame to a different sheet
        tidy_levies_info.to_excel(writer, sheet_name="Levies results", index=False)
        tidy_tariffs_info.to_excel(writer, sheet_name="Tariffs results", index=False)
        cost_ratio_df.to_excel(writer, sheet_name="Cost ratios", index=False)
        tidy_consumers_info.to_excel(
            writer, sheet_name="Consumers results", index=False
        )
        support_info_df.to_excel(
            writer, sheet_name="Support scenarios information", index=False
        )
        ofgem_archetypes_df.iloc[range(1, 25)].to_excel(
            writer, sheet_name="Archetypes data", index=False
        )
    print("Raw results data successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")


"""
Shaping consumers results for data visualisation table
"""

## Scenarios comparison dot plot
# Create pivot summary table
master_summary_flourish = tidy_consumers_info.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Support type",
        "Eligibility",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()

# Filter necessary columns
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "Support type",
        "Eligibility",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

# Rename columns for easier processing
master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
        "Support type": "SupportType",
    }
)

# Add unique levy reform and support scenario ID
master_summary_flourish["ScenarioSupport"] = (
    master_summary_flourish["Scenario"] + " + " + master_summary_flourish["SupportType"]
)

# Add unique levy reform, support scenario and eligibility ID
master_summary_flourish["ScenarioSupportEligibility"] = (
    master_summary_flourish["ScenarioSupport"]
    + " + "
    + master_summary_flourish["EligibleForSupport"].astype(str)
)

# Add reader-friendly scenario description
scenario_label = {
    f"{scenario_description.get('status quo')} + Flat rebate + False": "Status quo - WHD - Flat rebate - Ineligible",
    f"{scenario_description.get('status quo')} + Flat rebate + True": "Status quo - WHD - Flat rebate - Eligible",
    f"{scenario_description.get('rebalanced')} + Flat rebate + False": "Rebalancing - WHD - Flat rebate - Ineligible",
    f"{scenario_description.get('rebalanced')} + Flat rebate + True": "Rebalancing - WHD - Flat rebate - Eligible",
    f"{scenario_description.get('scenario_1')} + Unit discount on gas and electricity + False": "CORE (original) - Ineligible",
    f"{scenario_description.get('scenario_1')} + Unit discount on gas and electricity + True": "CORE (original) - Eligible",
    f"{scenario_description.get('scenario_2')} + Unit discount on gas and electricity + False": "CORE (alt) - Ineligible",
    f"{scenario_description.get('scenario_2')} + Unit discount on gas and electricity + True": "CORE (alt) - Eligible",
    f"{scenario_description.get('scenario_3')} + Unit discount on gas and electricity + False": "CORE + Remove GBIS - Ineligible",
    f"{scenario_description.get('scenario_3')} + Unit discount on gas and electricity + True": "CORE + Remove GBIS - Eligible",
    f"{scenario_description.get('scenario_4')} + Unit discount on gas and electricity + False": "CORE + Remove GBIS + 1/3 ECO4 - Ineligible",
    f"{scenario_description.get('scenario_4')} + Unit discount on gas and electricity + True": "CORE + Remove GBIS + 1/3 ECO4 - Eligible",
    f"{scenario_description.get('scenario_6')} + Unit discount on gas and electricity + False": "CORE + 1/2 WHD (original) - Ineligible",
    f"{scenario_description.get('scenario_6')} + Unit discount on gas and electricity + True": "CORE + 1/2 WHD (original) - Eligible",
    f"{scenario_description.get('scenario_7')} + Unit discount on gas and electricity + False": "CORE + 1/2 WHD (alt) - Ineligible",
    f"{scenario_description.get('scenario_7')} + Unit discount on gas and electricity + True": "CORE + 1/2 WHD (alt) - Eligible",
    f"{scenario_description.get('scenario_8')} + Unit discount on gas and electricity + False": "CORE + 1/2 WHD + Remove GBIS - Ineligible",
    f"{scenario_description.get('scenario_8')} + Unit discount on gas and electricity + True": "CORE + 1/2 WHD + Remove GBIS - Eligible",
    f"{scenario_description.get('scenario_12')} + Unit discount on gas and electricity + False": "CORE + Remove WHD + GBIS - Ineligible",
    f"{scenario_description.get('scenario_12')} + Unit discount on gas and electricity + True": "CORE + Remove WHD + GBIS - Eligible",
    f"{scenario_description.get('scenario_9')} + Unit discount on gas and electricity + False": "CORE + 1/2 WHD + Remove GBIS + 1/3 ECO4 - Ineligible",
    f"{scenario_description.get('scenario_9')} + Unit discount on gas and electricity + True": "CORE + 1/2 WHD + Remove GBIS + 1/3 ECO4 - Eligible",
    f"{scenario_description.get('scenario_11')} + Unit discount on gas and electricity + False": "CORE + Remove GBIS + ECO4 (original) - Ineligible",
    f"{scenario_description.get('scenario_11')} + Unit discount on gas and electricity + True": "CORE + Remove GBIS + ECO4 (original) - Eligible",
    f"{scenario_description.get('scenario_5')} + Unit discount on gas and electricity + False": "CORE + Remove GBIS + ECO4 (alt) - Ineligible",
    f"{scenario_description.get('scenario_5')} + Unit discount on gas and electricity + True": "CORE + Remove GBIS + ECO4 (alt) - Eligible",
    f"{scenario_description.get('scenario_10')} + Unit discount on gas and electricity + False": "CORE + 1/2 WHD + Remove GBIS + ECO4 - Ineligible",
    f"{scenario_description.get('scenario_10')} + Unit discount on gas and electricity + True": "CORE + 1/2 WHD + Remove GBIS + ECO4 - Eligible",
}
master_summary_flourish["ScenarioLabel"] = master_summary_flourish[
    "ScenarioSupportEligibility"
].map(scenario_label)

# Add group sizes
eligibility_size_lookup = {
    "WHD": scaled_whd_sizes,
    "CWP": cwp_sizes,
}
group_sizes = []
for row in master_summary_flourish.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
master_summary_flourish.loc[:, "GroupSize"] = group_sizes

# Add archetype sizes
archetype_sizes = ofgem_archetypes_scheme_eligibility_df[
    ["AnnualConsumptionProfile", "ArchetypeSize"]
]
archetype_sizes = archetype_sizes.rename(
    columns={
        "AnnualConsumptionProfile": "Name",
    }
)
master_summary_flourish = master_summary_flourish.merge(
    archetype_sizes, on="Name", how="left"
)

# Create new column for bill change from chosen baseline
baseline_scenario = "Status quo + Flat rebate"

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["ScenarioSupport"] == baseline_scenario)
        & (master_summary_flourish["EligibleForSupport"] == row.EligibleForSupport),
        "combined_fuel_bill",
    ].values
    # Ensure a baseline bill exists before subtracting
    baseline_bill = baseline_bill[0] if len(baseline_bill) > 0 else None
    # Compute the bill change or assign NaN if no baseline bill found
    bill_changes.append(
        row.combined_fuel_bill - baseline_bill if baseline_bill is not None else None
    )
master_summary_flourish.loc[:, "Net change in annual energy bill"] = bill_changes

# Specify order
scenario_order = [scenario for scenario in scenario_label.keys()]
master_summary_flourish = (
    master_summary_flourish.assign(
        ScenarioRank=master_summary_flourish["ScenarioSupportEligibility"].map(
            {s: i for i, s in enumerate(scenario_order)}
        )
    )
    .sort_values(["ScenarioRank", "Name", "EligibleForSupport"])
    .drop(columns=["ScenarioRank"])
    .reset_index(drop=True)
)

# Add support information
lookup_df = support_info_df.rename(columns={"Levy reform": "Scenario"})
master_summary_flourish = pd.merge(
    master_summary_flourish, lookup_df, on="Scenario", how="left"
)


## Individual scenario dot plot
# Helper function
def create_table_for_flourish(
    master_df: pd.DataFrame, scenario_name: str
) -> pd.DataFrame:

    # Filter for scenario of interest
    table = (
        master_df[master_df["ScenarioSupport"] == scenario_name]
        .sort_values(["EligibleForSupport", "Name"])
        .reset_index(drop=True)
    )

    # Add new "Group" column for consistency
    table["Group"] = table.apply(
        lambda row: (row.Name + "b" if row.EligibleForSupport else row.Name),
        axis=1,
    )

    # Add archetypes information
    archetypes_information = {
        "A1": "75+ single pensioners, lowest income, owner-occupiers",
        "A2": "55+ single adults on lowest incomes, in social housing",
        "A3": "Low income adults 45-65 with disability, in social housing",
        "B4": "75+ single pensioners, lowest income, electrical heating - owner-occupiers or social housing",
        "B5": "Adults 45+ with disability, low income, mixed tenure with electrical or other heating",
        "B6": "Low-income adults in privately rented or social housing",
        "C7": "Low-middle income families with children, in social housing, high BAME proportion",
        "C8": "Low-middle income families with 1 child, in social housing with electrical heating, high BAME proportion",
        "C9": "Mostly pensioner singles/couples 55+ low-middle income, owner occupiers",
        "D10": "Couples 55+ with disability, owner occupiers",
        "D11": "Middle income singles/couples in purpose-built flats with good EPC",
        "D12": "Pensioners in large detached houses, mid (but mixed) income",
        "E13": "Families with disabilities, mixed income and mixed tenure",
        "E14": "Families on middle income in rented or own homes",
        "F15": "Families on middle income in rented or own homes using 'other' fuel or electricity",
        "F16": "Middle-income young professionals in modern flats with good EPC, electrical heating",
        "G17": "Adults 45+ in Welsh unconventional housing using oil and other fuels with highest fuel expenditure, mixed income",
        "G18": "Couples or multiple adults using 'other' fuels for heating",
        "H19": "Middle-upper income couples in rural oil-heated homes",
        "H20": "High-income adults, mainly owner occupiers (largest archetype)",
        "I21": "High income families with 1 child, owner occupiers",
        "I22": "High income adults with no children, owner occupiers",
        "J23": "High income adults 45+, owner occupiers of large detached houses",
        "J24": "Highest income families in rural oil-heated homes",
    }
    table["Information"] = table["Name"].map(archetypes_information)

    # # Add households information
    # table["Households"] = table.apply(
    #     lambda row: f"{round(row.GroupSize):,} ({round((row.GroupSize / row.ArchetypeSize) * 100, 1)}% of archetype)",
    #     axis=1,
    # )

    # Modify fuel column
    table["Main Fuel"] = table.apply(
        lambda row: (
            "Warm Home Discount recipients"
            if row.EligibleForSupport
            else row.main_heating_fuel
        ),
        axis=1,
    )

    # Rename columns for clarity
    table = table.rename(
        columns={
            "Name": "Archetype",
        }
    )

    # Reorder columns
    table = table[
        [
            "Archetype",
            "Group",
            "Main Fuel",
            "GroupSize",
            "Net change in annual energy bill",
            "Information",
            "ScenarioSupport",
        ]
    ]

    # Add rows for plotting helper arrows
    arrow_rows = table.tail(24).copy()  # copies eligible values
    arrow_rows["Main Fuel"] = "Helper arrow"

    # Tailor the direction of arrow
    def adjust_energy_bill(row):

        matching_row = table[table["Archetype"] == row["Archetype"]]
        reference_value = matching_row["Net change in annual energy bill"].values[
            0
        ]  # ineligible value
        if reference_value > row["Net change in annual energy bill"]:
            if reference_value > 0:
                difference = abs(reference_value) + abs(
                    row["Net change in annual energy bill"]
                )
                return row["Net change in annual energy bill"] + (difference * 0.1)
            else:
                difference = abs(row["Net change in annual energy bill"]) - abs(
                    reference_value
                )
                return row["Net change in annual energy bill"] + (difference * 0.3)
        else:
            difference = abs(reference_value) - abs(
                row["Net change in annual energy bill"]
            )
            return row["Net change in annual energy bill"] - (difference * 0.5)

    arrow_rows["Net change in annual energy bill"] = arrow_rows.apply(
        adjust_energy_bill, axis=1
    )

    arrow_rows["Group"] = arrow_rows["Group"].str.replace("b", "")
    table = pd.concat([table, arrow_rows], ignore_index=True)

    return table


# List of unique levy reform and support scenarios
unique_scenarios = master_summary_flourish["ScenarioSupport"].unique().tolist()
unique_scenarios.remove("Status quo + Flat rebate")

# Create table for Flourish chart for each scenario
scenario_tables = {}
for scenario in unique_scenarios:
    scenario_table = create_table_for_flourish(master_summary_flourish, scenario)
    scenario_tables[scenario] = scenario_table


"""
Weighted averages for (i) gas-using households, eligible for support, (ii) gas-using households, ineligible for support, (iii) all others
"""

# Gas, eligible
eligible_gas_df = master_summary_flourish[
    (master_summary_flourish["EligibleForSupport"] == True)
    & (master_summary_flourish["main_heating_fuel"] == "Gas")
]
# Minimum for each scenario
eligible_gas_min = (
    pd.DataFrame(
        eligible_gas_df.groupby("Scenario")["Net change in annual energy bill"].min()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Minimum"}, inplace=False)
)
# Maximum for each scenario
eligible_gas_max = (
    pd.DataFrame(
        eligible_gas_df.groupby("Scenario")["Net change in annual energy bill"].max()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Maximum"}, inplace=False)
)
# Weighted average for each scenario
eligible_gas_weighted_avg = (
    eligible_gas_df.groupby("Scenario", group_keys=False)
    .apply(
        lambda x: (x["Net change in annual energy bill"] * x["GroupSize"]).sum()
        / x["GroupSize"].sum()
    )
    .reset_index(name="Weighted average")
)
# Merge into summary table
eligible_gas_summary = pd.merge(
    eligible_gas_min, eligible_gas_max, on="Scenario", how="left"
).merge(eligible_gas_weighted_avg, on="Scenario", how="left")
eligible_gas_summary["Group"] = "Eligible gas"
eligible_gas_summary = eligible_gas_summary.melt(
    id_vars=["Scenario", "Group"], var_name="Statistic"
)


# Gas, ineligible
ineligible_gas_df = master_summary_flourish[
    (master_summary_flourish["EligibleForSupport"] == False)
    & (master_summary_flourish["main_heating_fuel"] == "Gas")
]
# Minimum for each scenario
ineligible_gas_min = (
    pd.DataFrame(
        ineligible_gas_df.groupby("Scenario")["Net change in annual energy bill"].min()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Minimum"}, inplace=False)
)
# Maximum for each scenario
ineligible_gas_max = (
    pd.DataFrame(
        ineligible_gas_df.groupby("Scenario")["Net change in annual energy bill"].max()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Maximum"}, inplace=False)
)
# Weighted average for each scenario
ineligible_gas_weighted_avg = (
    ineligible_gas_df.groupby("Scenario", group_keys=False)
    .apply(
        lambda x: (x["Net change in annual energy bill"] * x["GroupSize"]).sum()
        / x["GroupSize"].sum()
    )
    .reset_index(name="Weighted average")
)
# Merge into summary table
ineligible_gas_summary = pd.merge(
    ineligible_gas_min, ineligible_gas_max, on="Scenario", how="left"
).merge(ineligible_gas_weighted_avg, on="Scenario", how="left")
ineligible_gas_summary["Group"] = "Ineligible gas"
ineligible_gas_summary = ineligible_gas_summary.melt(
    id_vars=["Scenario", "Group"], var_name="Statistic"
)

# All others
others_df = master_summary_flourish[
    master_summary_flourish["main_heating_fuel"] != "Gas"
]
# Minimum for each scenario
others_min = (
    pd.DataFrame(
        others_df.groupby("Scenario")["Net change in annual energy bill"].min()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Minimum"}, inplace=False)
)
# Maximum for each scenario
others_max = (
    pd.DataFrame(
        others_df.groupby("Scenario")["Net change in annual energy bill"].max()
    )
    .reset_index()
    .rename(columns={"Net change in annual energy bill": "Maximum"}, inplace=False)
)
# Weighted average for each scenario
others_weighted_avg = (
    others_df.groupby("Scenario", group_keys=False)
    .apply(
        lambda x: (x["Net change in annual energy bill"] * x["GroupSize"]).sum()
        / x["GroupSize"].sum()
    )
    .reset_index(name="Weighted average")
)
# Merge into summary table
others_summary = pd.merge(others_min, others_max, on="Scenario", how="left").merge(
    others_weighted_avg, on="Scenario", how="left"
)
others_summary["Group"] = "All others"
others_summary = others_summary.melt(
    id_vars=["Scenario", "Group"], var_name="Statistic"
)

# Combine into master summary table
bill_range_summary = pd.concat(
    [eligible_gas_summary, ineligible_gas_summary, others_summary]
)


"""
Saving Flourish data tables to Excel
"""
flourish_filename = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_5_flourish.xlsx"
)
try:
    with pd.ExcelWriter(flourish_filename, engine="xlsxwriter") as writer:
        # Master scenario tables
        master_summary_flourish.to_excel(
            writer, sheet_name="Master summary", index=False
        )
        # Bill range summary
        bill_range_summary.to_excel(
            writer, sheet_name="Bill change ranges", index=False
        )
        # Individual scenario tables
        i = 1
        for scenario in unique_scenarios:
            scenario_tables[scenario].to_excel(
                writer, sheet_name=f"Scenario_chart_{i}", index=False
            )
            i = i + 1
    print("Tables for Flourish successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")


"""
Creating histograms and saving to file
"""


# Helper function
def create_weighted_histogram_dataframe(
    df: pd.DataFrame,
    scenario_support_name: str,
    eligible_only: bool = True,
):
    # Define custom bins from -750 to 250 with intervals of 50
    bins = np.arange(-850, 451, 50)
    bin_labels = pd.IntervalIndex.from_breaks(bins, closed="left")

    if eligible_only:
        df = df.loc[
            (df["ScenarioSupport"] == scenario_support_name)
            & (df["EligibleForSupport"] == True)
        ].copy()
    else:
        df = df.loc[df["ScenarioSupport"] == scenario_support_name].copy()

    # Bin data using defined bins
    df.loc[:, "binned"] = pd.cut(
        df["Net change in annual energy bill"], bins=bin_labels
    )

    # Aggregate by bin and heating fuel type
    grouped_df = (
        df.groupby(["binned", "main_heating_fuel"], observed=True)
        .agg({"GroupSize": "sum"})
        .reset_index()
    )

    # Pivot and reindex
    pivot_df = grouped_df.pivot(
        index="binned", columns="main_heating_fuel", values="GroupSize"
    ).reindex(bin_labels, fill_value=np.nan)

    # Ensure all heating fuel columns are present
    all_fuel_types = df["main_heating_fuel"].unique()
    pivot_df = pivot_df.reindex(columns=all_fuel_types, fill_value=np.nan)

    # Rename the index to include the scenario support name
    pivot_df = pivot_df.rename_axis(index=scenario_support_name)

    return pivot_df[["Gas", "Electricity", "Electricity/Other", "Other"]]


# Create dataframes for all scenarios
scenario_names = master_summary_flourish["ScenarioSupport"].unique().tolist()
scenario_histogram_tables = {}
for scenario in scenario_names:
    scenario_histogram_tables[scenario] = create_weighted_histogram_dataframe(
        df=master_summary_flourish, scenario_support_name=scenario, eligible_only=False
    )

histograms_filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_5_histogram_tables.xlsx"
try:
    with pd.ExcelWriter(histograms_filename, engine="xlsxwriter") as writer:
        # Individual scenario tables
        i = 1
        for scenario in scenario_names:
            scenario_histogram_tables[scenario].to_excel(
                writer, sheet_name=f"Histogram_scenario_{i}", index=True
            )
            i = i + 1
    print("Histogram tables for Flourish successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")
