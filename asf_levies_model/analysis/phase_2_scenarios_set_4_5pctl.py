"""

Phase 2, Set 4 scenarios

All scenarios have:
- Rebalancing RO + FiT to gas
- WHD target spending on core group = £1.6 billion, WHD for industry initiatives = £50 million
- WHD applied as a unit discount to both gas and electricity, with the discount values calculated using
  shares of target spending allocated based on shares of eligible consumption
- Eligibility group is Cold Weather Payments
This set-up will be referred to as "Base".

Scenarios (name of corresponding ConsumerCollection):
00. Status quo (status_quo_consumers_flat_rebate)
0. Rebalancing only with no changes to WHD (rebalanced_consumers_flat_rebate)
1. Base (base_consumers_unit_discount)
2. Base + Remove GBIS to general taxation (base_delete_gbis_consumers_unit_discount)
3. Base + Remove ECO (ECO4+GBIS) to general taxation (base_delete_eco_consumers_unit_discount)
4. Base + WHD levy revenue allocation of 1/2 on energy bills and 1/2 on general taxation (base_half_whd_consumers_unit_discount)
5. Base + WHD levy revenue allocation of 1/3 on energy bills and 2/3 on general taxation (base_third_whd_consumers_unit_discount)
6. Base + Remove WHD to general taxation (base_delete_whd_consumers_unit_discount)

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

# Create 5th Percentile columns to use in consumer collection
# Basically a selective unstacking.
lookup_5pct = (
    ofgem_archetypes_df.loc[
        lambda df: df["AnnualConsumptionProfile"].isin(
            [
                "A1_5PCT",
                "A2_5PCT",
                "A3_5PCT",
                "B4_5PCT",
                "B5_5PCT",
                "B6_5PCT",
                "C7_5PCT",
                "C8_5PCT",
                "C9_5PCT",
                "D10_5PCT",
                "D11_5PCT",
                "D12_5PCT",
                "E13_5PCT",
                "E14_5PCT",
                "F15_5PCT",
                "F16_5PCT",
                "G17_5PCT",
                "G18_5PCT",
                "H19_5PCT",
                "H20_5PCT",
                "I21_5PCT",
                "I22_5PCT",
                "J23_5PCT",
                "J24_5PCT",
            ]
        ),
        ["AnnualConsumptionProfile", "ElectricitySingleRatekWh", "GaskWh"],
    ]
    .assign(
        AnnualConsumptionProfile=lambda df: df["AnnualConsumptionProfile"].str.split(
            "_", expand=True
        )[0]
    )
    .rename(
        columns={
            "ElectricitySingleRatekWh": "ElectricitySingleRatekWh_5PCT",
            "GaskWh": "GaskWh_5PCT",
        }
    )
)
# Merge lookup_5pct with ofgem_archetypes_df
ofgem_archetypes_df = ofgem_archetypes_df.merge(
    lookup_5pct, how="left", on="AnnualConsumptionProfile"
)

status_quo_consumers = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
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
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
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
Defining new WHD revenue parameters
"""
new_whd_core = 1_600_000_000
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
Defining unit discount parameters
Constant across all scenarios as WHD revenue is constant
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

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
cwp_core_target_spending_electricity_weight = cwp_recipients_electricity_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)
cwp_core_target_spending_gas_weight = cwp_recipients_gas_consumption / (
    cwp_recipients_electricity_consumption + cwp_recipients_gas_consumption
)

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    new_whd_core * cwp_core_target_spending_electricity_weight
)
core_target_spending_gas = new_whd_core * cwp_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_electricity = (
    core_target_spending_electricity / cwp_recipients_electricity_consumption
) * 1.05
unit_discount_gas = core_target_spending_gas / cwp_recipients_gas_consumption * 1.05

"""
1. Base
"""

# Update revenue
base_pc = rebalanced_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_gas_tariff = gas_tariff.update_policy_costs(base_pc)
base_electricity_tariff = electricity_tariff.update_policy_costs(base_pc)

# Create ConsumerCollection
base_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_gas_tariff,
    electricity_tariff=base_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_consumers_unit_discount = base_consumers.apply_support_to_eligible_consumers(
    "electricity",
    unit_discount_electricity,
    "unit discount",
    inplace=False,
).apply_support_to_eligible_consumers(
    "gas", unit_discount_gas, "unit discount", inplace=False
)


"""
2. Base and remove GBIS to general taxation
"""

# Add rebalancing weights for GBIS to existing rebalancing dictionary for RO and FiT
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
base_delete_gbis_pc = pc.rebalance_levies(
    rebalancing_weights_delete_gbis,
    scenario_name="rebalance_ro_fit_to_gas_gbis_to_tax",
)

# Update revenue
base_delete_gbis_pc = base_delete_gbis_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_delete_gbis_gas_tariff = gas_tariff.update_policy_costs(base_delete_gbis_pc)
base_delete_gbis_electricity_tariff = electricity_tariff.update_policy_costs(
    base_delete_gbis_pc
)

# Create ConsumerCollection
base_delete_gbis_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_delete_gbis_gas_tariff,
    electricity_tariff=base_delete_gbis_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_gbis_consumers_unit_discount = (
    base_delete_gbis_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

"""
3. Base and remove ECO (ECO4 and GBIS) to general taxation
"""

# Add rebalancing weights for ECO4 to existing rebalancing dictionary for RO, FiT and GBIS
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
base_delete_eco_pc = pc.rebalance_levies(
    rebalancing_weights_delete_eco,
    scenario_name="rebalance_ro_fit_to_gas_eco_to_tax",
)

# Update revenue
base_delete_eco_pc = base_delete_eco_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_delete_eco_gas_tariff = gas_tariff.update_policy_costs(base_delete_eco_pc)
base_delete_eco_electricity_tariff = electricity_tariff.update_policy_costs(
    base_delete_eco_pc
)

# Create ConsumerCollection
base_delete_eco_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with ECO on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_delete_eco_gas_tariff,
    electricity_tariff=base_delete_eco_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_eco_consumers_unit_discount = (
    base_delete_eco_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

"""
4. Base with rebalancing WHD levy to 1/2 on general taxation and 1/2 on energy bills
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
base_half_whd_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_half_to_tax",
)

# Update revenue
base_half_whd_pc = base_half_whd_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_half_whd_gas_tariff = gas_tariff.update_policy_costs(base_half_whd_pc)
base_half_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_half_whd_pc
)

# Create ConsumerCollection
base_half_whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_consumers_unit_discount = (
    base_half_whd_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)


"""
5. Base with rebalancing WHD levy to 2/3 on general taxation and 1/3 on energy bills
"""

# Calculate new revenue weights for gas and electricity, scale down current weights from 1 to 1/3
new_whd_gas_weight = pc["whd"].gas_weight * (1 / 3)
new_whd_elec_weight = (1 / 3) - new_whd_gas_weight

# Add rebalancing weights for WHD to existing rebalancing dictionary for RO and FiT
rebalancing_weights_third_whd = copy.deepcopy(rebalancing_weights)
rebalancing_weights_third_whd["whd"] = {
    "new_electricity_weight": new_whd_elec_weight,
    "new_gas_weight": new_whd_gas_weight,
    "new_tax_weight": 2 / 3,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 1,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 1,
}

# Apply rebalancing weights
base_third_whd_pc = pc.rebalance_levies(
    rebalancing_weights_third_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_third_to_tax",
)

# Update revenue
base_third_whd_pc = base_third_whd_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_third_whd_gas_tariff = gas_tariff.update_policy_costs(base_third_whd_pc)
base_third_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_third_whd_pc
)

# Create ConsumerCollection
base_third_whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with 2/3 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_third_whd_gas_tariff,
    electricity_tariff=base_third_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_third_whd_consumers_unit_discount = (
    base_third_whd_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

"""
5. Base + Remove WHD to general taxation
"""

# Add rebalancing weights for WHD to existing rebalancing dictionary for RO and FiT
rebalancing_weights_delete_whd = copy.deepcopy(rebalancing_weights)
rebalancing_weights_delete_whd["whd"] = {
    "new_electricity_weight": 0,
    "new_gas_weight": 0,
    "new_tax_weight": 1,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
base_delete_whd_pc = pc.rebalance_levies(
    rebalancing_weights_delete_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_to_tax",
)

# Update revenue
base_delete_whd_pc = base_delete_whd_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_delete_whd_gas_tariff = gas_tariff.update_policy_costs(base_delete_whd_pc)
base_delete_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_delete_whd_pc
)

# Create ConsumerCollection
base_delete_whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with WHD on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_5PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_5PCT",
    gas_tariff=base_delete_whd_gas_tariff,
    electricity_tariff=base_delete_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_whd_consumers_unit_discount = (
    base_delete_whd_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

print(unit_discount_electricity, unit_discount_gas)
"""
Printing outputs
"""

scenario_description = {
    "status quo": "Status quo",
    "rebalanced": "Rebalance RO+FiT to gas",
    "base": "CORE",
    "base_delete_gbis": "CORE + GBIS to tax",
    "base_delete_eco": "CORE + ECO to tax",
    "base_half_whd": "CORE + 1/2 WHD revenue to tax",
    "base_third_whd": "CORE + 2/3 WHD revenue to tax",
    "base_delete_whd": "CORE + WHD to tax",
}

# Information about levies
levy_collections = {
    pc: scenario_description.get("status quo"),
    rebalanced_pc: scenario_description.get("rebalanced"),
    base_pc: scenario_description.get("base"),
    base_delete_gbis_pc: scenario_description.get("base_delete_gbis"),
    base_delete_eco_pc: scenario_description.get("base_delete_eco"),
    base_half_whd_pc: scenario_description.get("base_half_whd"),
    base_third_whd_pc: scenario_description.get("base_third_whd"),
    base_delete_whd_pc: scenario_description.get("base_delete_whd"),
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
    base_gas_tariff: scenario_description.get("base"),
    base_electricity_tariff: scenario_description.get("base"),
    base_delete_gbis_gas_tariff: scenario_description.get("base_delete_gbis"),
    base_delete_gbis_electricity_tariff: scenario_description.get("base_delete_gbis"),
    base_delete_eco_gas_tariff: scenario_description.get("base_delete_eco"),
    base_delete_eco_electricity_tariff: scenario_description.get("base_delete_eco"),
    base_half_whd_gas_tariff: scenario_description.get("base_half_whd"),
    base_half_whd_electricity_tariff: scenario_description.get("base_half_whd"),
    base_third_whd_gas_tariff: scenario_description.get("base_third_whd"),
    base_third_whd_electricity_tariff: scenario_description.get("base_third_whd"),
    base_delete_whd_gas_tariff: scenario_description.get("base_third_whd"),
    base_delete_whd_electricity_tariff: scenario_description.get("base_third_whd"),
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
    (
        rebalanced_electricity_tariff,
        rebalanced_gas_tariff,
    ): scenario_description.get("rebalanced"),
    (
        base_electricity_tariff,
        base_gas_tariff,
    ): scenario_description.get("base"),
    (
        base_delete_gbis_electricity_tariff,
        base_delete_gbis_gas_tariff,
    ): scenario_description.get("base_delete_gbis"),
    (
        base_delete_eco_electricity_tariff,
        base_delete_eco_gas_tariff,
    ): scenario_description.get("base_delete_eco"),
    (
        base_half_whd_electricity_tariff,
        base_half_whd_gas_tariff,
    ): scenario_description.get("base_half_whd"),
    (
        base_third_whd_electricity_tariff,
        base_third_whd_gas_tariff,
    ): scenario_description.get("base_third_whd"),
    (
        base_delete_whd_electricity_tariff,
        base_delete_whd_gas_tariff,
    ): scenario_description.get("base_delete_whd"),
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
    base_consumers_unit_discount: scenario_description.get("base"),
    base_delete_gbis_consumers_unit_discount: scenario_description.get(
        "base_delete_gbis"
    ),
    base_delete_eco_consumers_unit_discount: scenario_description.get(
        "base_delete_eco"
    ),
    base_half_whd_consumers_unit_discount: scenario_description.get("base_half_whd"),
    base_third_whd_consumers_unit_discount: scenario_description.get("base_third_whd"),
    base_delete_whd_consumers_unit_discount: scenario_description.get(
        "base_delete_whd"
    ),
}

consumer_collections_support_type = {
    status_quo_consumers_flat_rebate: "Flat rebate",
    rebalanced_consumers_flat_rebate: "Flat rebate",
    base_consumers_unit_discount: "Unit discount on gas and electricity",
    base_delete_gbis_consumers_unit_discount: "Unit discount on gas and electricity",
    base_delete_eco_consumers_unit_discount: "Unit discount on gas and electricity",
    base_half_whd_consumers_unit_discount: "Unit discount on gas and electricity",
    base_third_whd_consumers_unit_discount: "Unit discount on gas and electricity",
    base_delete_whd_consumers_unit_discount: "Unit discount on gas and electricity",
}

consumer_collections_eligibility = {
    status_quo_consumers_flat_rebate: "WHD",
    rebalanced_consumers_flat_rebate: "WHD",
    base_consumers_unit_discount: "CWP",
    base_delete_gbis_consumers_unit_discount: "CWP",
    base_delete_eco_consumers_unit_discount: "CWP",
    base_half_whd_consumers_unit_discount: "CWP",
    base_third_whd_consumers_unit_discount: "CWP",
    base_delete_whd_consumers_unit_discount: "CWP",
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

rebalanced_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD revenue x 1",
            "Targeted group": "WHD",
            "Public spend (£ per year)": rebalanced_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": rebalanced_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": new_whd_core,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": None,
            "WHD target spend on gas consumption of target households (£)": None,
            "Total electricity consumption of target households (MWh)": None,
            "Total gas consumption of target households (MWh)": None,
            "Flat rebate (£)": 150,
        }
    ]
)
base_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas / base_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_delete_gbis_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_delete_gbis"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_delete_gbis_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_delete_gbis_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_delete_gbis_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_delete_gbis_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_delete_gbis_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_delete_eco_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_delete_eco"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_delete_eco_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_delete_eco_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_delete_eco_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_delete_eco_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_delete_eco_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_half_whd_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_half_whd"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_half_whd_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_half_whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_half_whd_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_half_whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_half_whd_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_third_whd_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_third_whd"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_third_whd_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_third_whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_third_whd_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_third_whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_third_whd_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_delete_whd_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_delete_whd"),
            "Targeted group": "CWP",
            "Public spend (£ per year)": base_delete_whd_pc.union_levies().general_taxation,
            "WHD revenue (£ per year)": base_delete_whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_delete_whd_pc["whd"].revenue
            - whd_industry_initiatives,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_electricity,
            "Unit discount gas (£/MWh)": unit_discount_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_electricity
                / base_delete_whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_delete_whd_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
support_info_df = pd.concat(
    [
        support_info_df,
        rebalanced_row,
        base_row,
        base_delete_gbis_row,
        base_delete_eco_row,
        base_half_whd_row,
        base_third_whd_row,
        base_delete_whd_row,
    ]
)

"""
Saving raw results data to Excel
"""
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_4_5pct.xlsx"

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
    f"{scenario_description.get('base')} + Unit discount on gas and electricity + False": "CORE - Ineligible",
    f"{scenario_description.get('base')} + Unit discount on gas and electricity + True": "CORE - Eligible",
    f"{scenario_description.get('base_variable_whd')} + Unit discount on gas and electricity + False": "CORE - WHD variable charge - Ineligible",
    f"{scenario_description.get('base_variable_whd')} + Unit discount on gas and electricity + True": "CORE - WHD variable charge - Eligible",
    f"{scenario_description.get('base_delete_gbis')} + Unit discount on gas and electricity + False": "CORE - GBIS to tax - Ineligible",
    f"{scenario_description.get('base_delete_gbis')} + Unit discount on gas and electricity + True": "CORE - GBIS to tax - Eligible",
    f"{scenario_description.get('base_delete_eco')} + Unit discount on gas and electricity + False": "CORE - ECO4+GBIS to tax - Ineligible",
    f"{scenario_description.get('base_delete_eco')} + Unit discount on gas and electricity + True": "CORE - ECO4+GBIS to tax - Eligible",
    f"{scenario_description.get('base_half_whd')} + Unit discount on gas and electricity + False": "CORE - 1/2 WHD to tax - Ineligible",
    f"{scenario_description.get('base_half_whd')} + Unit discount on gas and electricity + True": "CORE - 1/2 WHD to tax - Eligible",
    f"{scenario_description.get('base_third_whd')} + Unit discount on gas and electricity + False": "CORE - 2/3 WHD to tax - Ineligible",
    f"{scenario_description.get('base_third_whd')} + Unit discount on gas and electricity + True": "CORE - 2/3 WHD to tax - Eligible",
    f"{scenario_description.get('base_delete_whd')} + Unit discount on gas and electricity + False": "CORE - WHD to tax - Ineligible",
    f"{scenario_description.get('base_delete_whd')} + Unit discount on gas and electricity + True": "CORE - WHD to tax - Eligible",
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
scenario_order = [scenario for scenario in scenario_description.values()]
master_summary_flourish = (
    master_summary_flourish.assign(
        ScenarioRank=master_summary_flourish["Scenario"].map(
            {s: i for i, s in enumerate(scenario_order)}
        )
    )
    .sort_values(["ScenarioRank", "Name", "EligibleForSupport"])
    .drop(columns=["ScenarioRank"])
    .reset_index(drop=True)
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

    # Add households information
    table["Households"] = table.apply(
        lambda row: f"{round(row.GroupSize):,} ({round((row.GroupSize / row.ArchetypeSize) * 100, 1)}% of archetype)",
        axis=1,
    )

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
            "Households",
            "Net change in annual energy bill",
            "Information",
            "ScenarioSupport",
        ]
    ]

    # Add rows for plotting helper arrows
    arrow_rows = table.tail(24).copy()
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
Saving Flourish data tables to Excel
"""
flourish_filename = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_4_5pct_flourish.xlsx"
)
try:
    with pd.ExcelWriter(flourish_filename, engine="xlsxwriter") as writer:
        # Master scenario tables
        master_summary_flourish.to_excel(
            writer, sheet_name="Master summary", index=False
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

histograms_filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_4_5pct_histogram_tables.xlsx"
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
