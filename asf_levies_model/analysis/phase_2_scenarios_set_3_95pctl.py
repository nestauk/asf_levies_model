"""

Phase 2, Set 3 scenarios

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
2. Base + WHD levy to variable charge on gas and electricity (base_variable_whd_consumers_unit_discount)
3a. Base + Remove GBIS to general taxation (base_delete_gbis_consumers_unit_discount)
3b. Base + Remove ECO (ECO4+GBIS) to general taxation (base_delete_eco_consumers_unit_discount)
4. Base + WHD levy revenue allocation of 1/3 on energy bills and 2/3 on general taxation (base_partial_whd_consumers_unit_discount)

"""

import pandas as pd
from datetime import datetime
import copy

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
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
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
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
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
)
unit_discount_gas = core_target_spending_gas / cwp_recipients_gas_consumption


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
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
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
2. Base with rebalancing WHD levy to variable charge on gas and electricity
"""

# For current standing charge, revenue weights for WHD is based on shares of gas and electricity *customers*
# This leads to the same standing charges for both gas and electricity
# Moving to variable charges, let's assume we want to retain the same behaviour of equal unit costs for gas and electricity

# Calculate revenue weights based on gas and electricity *consumption*
new_whd_gas_weight = supply_gas / (supply_gas + supply_elec)
new_whd_electricity_weight = 1 - new_whd_gas_weight


# Add rebalancing weights for WHD to existing rebalancing dictionary for RO and FiT
rebalancing_weights_variable_whd = copy.deepcopy(rebalancing_weights)
rebalancing_weights_variable_whd["whd"] = {
    "new_electricity_weight": new_whd_electricity_weight,
    "new_gas_weight": new_whd_gas_weight,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# Alternative: Keep revenue weights the same
# rebalancing_weights_variable_whd["whd"] = {
#     "new_electricity_weight": pc["whd"].electricity_weight,
#     "new_gas_weight": pc["whd"].gas_weight,
#     "new_tax_weight": 0,
#     "new_variable_weight_elec": 1,
#     "new_fixed_weight_elec": 0,
#     "new_variable_weight_gas": 1,
#     "new_fixed_weight_gas": 0,
# }

# Apply rebalancing weights
base_variable_whd_pc = pc.rebalance_levies(
    rebalancing_weights_variable_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_to_variable",
)

# Update revenue
base_variable_whd_pc = base_variable_whd_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_variable_whd_gas_tariff = gas_tariff.update_policy_costs(base_variable_whd_pc)
base_variable_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_variable_whd_pc
)

# Create ConsumerCollection
base_variable_whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with WHD on variable charge",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=base_variable_whd_gas_tariff,
    electricity_tariff=base_variable_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_variable_whd_consumers_unit_discount = (
    base_variable_whd_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

"""
3a. Base and remove GBIS to general taxation
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
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
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
3b. Base and remove ECO (ECO4 and GBIS) to general taxation
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
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
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
4. Base with rebalancing WHD levy to 2/3 on general taxation and 1/3 on energy bills
"""

# Calculate new revenue weights for gas and electricity, scale down current weights from 1 to 1/3
new_whd_gas_weight = pc["whd"].gas_weight * (1 / 3)
new_whd_elec_weight = (1 / 3) - new_whd_gas_weight

# Add rebalancing weights for WHD to existing rebalancing dictionary for RO and FiT
rebalancing_weights_partial_whd = copy.deepcopy(rebalancing_weights)
rebalancing_weights_partial_whd["whd"] = {
    "new_electricity_weight": new_whd_elec_weight,
    "new_gas_weight": new_whd_gas_weight,
    "new_tax_weight": 2 / 3,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 1,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 1,
}

# Apply rebalancing weights
base_partial_whd_pc = pc.rebalance_levies(
    rebalancing_weights_partial_whd,
    scenario_name="rebalance_ro_fit_to_gas_whd_partial_to_tax",
)

# Update revenue
base_partial_whd_pc = base_partial_whd_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_partial_whd_gas_tariff = gas_tariff.update_policy_costs(base_partial_whd_pc)
base_partial_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_partial_whd_pc
)

# Create ConsumerCollection
base_partial_whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="CORE with 2/3 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=base_partial_whd_gas_tariff,
    electricity_tariff=base_partial_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_partial_whd_consumers_unit_discount = (
    base_partial_whd_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

"""
Printing outputs
"""

scenario_description = {
    "status quo": "Status quo",
    "rebalanced": "Rebalance RO+FiT to gas",
    "base": "CORE",
    "base_variable_whd": "CORE + WHD to variable charge",
    "base_delete_gbis": "CORE + GBIS to tax",
    "base_delete_eco": "CORE + ECO to tax",
    "base_partial_whd": "CORE + 2/3 WHD revenue raised from tax",
}

# Information about levies
levy_collections = {
    pc: scenario_description.get("status quo"),
    rebalanced_pc: scenario_description.get("rebalanced"),
    base_pc: scenario_description.get("base"),
    base_variable_whd_pc: scenario_description.get("base_variable_whd"),
    base_delete_gbis_pc: scenario_description.get("base_delete_gbis"),
    base_delete_eco_pc: scenario_description.get("base_delete_eco"),
    base_partial_whd_pc: scenario_description.get("base_partial_whd"),
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
    base_variable_whd_gas_tariff: scenario_description.get("base_variable_whd"),
    base_variable_whd_electricity_tariff: scenario_description.get("base_variable_whd"),
    base_delete_gbis_gas_tariff: scenario_description.get("base_delete_gbis"),
    base_delete_gbis_electricity_tariff: scenario_description.get("base_delete_gbis"),
    base_delete_eco_gas_tariff: scenario_description.get("base_delete_eco"),
    base_delete_eco_electricity_tariff: scenario_description.get("base_delete_eco"),
    base_partial_whd_gas_tariff: scenario_description.get("base_partial_whd"),
    base_partial_whd_electricity_tariff: scenario_description.get("base_partial_whd"),
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
        base_variable_whd_electricity_tariff,
        base_variable_whd_gas_tariff,
    ): scenario_description.get("base_variable_whd"),
    (
        base_delete_gbis_electricity_tariff,
        base_delete_gbis_gas_tariff,
    ): scenario_description.get("base_delete_gbis"),
    (
        base_delete_eco_electricity_tariff,
        base_delete_eco_gas_tariff,
    ): scenario_description.get("base_delete_eco"),
    (
        base_partial_whd_electricity_tariff,
        base_partial_whd_gas_tariff,
    ): scenario_description.get("base_partial_whd"),
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
    base_variable_whd_consumers_unit_discount: scenario_description.get(
        "base_variable_whd"
    ),
    base_delete_gbis_consumers_unit_discount: scenario_description.get(
        "base_delete_gbis"
    ),
    base_delete_eco_consumers_unit_discount: scenario_description.get(
        "base_delete_eco"
    ),
    base_partial_whd_consumers_unit_discount: scenario_description.get(
        "base_partial_whd"
    ),
}

consumer_collections_support_type = {
    status_quo_consumers_flat_rebate: "Flat rebate",
    rebalanced_consumers_flat_rebate: "Flat rebate",
    base_consumers_unit_discount: "Unit discount on gas and electricity",
    base_variable_whd_consumers_unit_discount: "Unit discount on gas and electricity",
    base_delete_gbis_consumers_unit_discount: "Unit discount on gas and electricity",
    base_delete_eco_consumers_unit_discount: "Unit discount on gas and electricity",
    base_partial_whd_consumers_unit_discount: "Unit discount on gas and electricity",
}

consumer_collections_eligibility = {
    status_quo_consumers_flat_rebate: "WHD",
    rebalanced_consumers_flat_rebate: "WHD",
    base_consumers_unit_discount: "CWP",
    base_variable_whd_consumers_unit_discount: "CWP",
    base_delete_gbis_consumers_unit_discount: "CWP",
    base_delete_eco_consumers_unit_discount: "CWP",
    base_partial_whd_consumers_unit_discount: "CWP",
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
rebalanced_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD revenue x 1",
            "Targeted group": "Support to WHD eligible, gas and electricity",
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
            "Targeted group": "Support to CWP eligible, gas and electricity",
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
base_variable_whd_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_variable_whd"),
            "Targeted group": "Support to CWP eligible, gas and electricity",
            "WHD revenue (£ per year)": base_variable_whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_variable_whd_pc["whd"].revenue
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
                / base_variable_whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_variable_whd_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
base_delete_gbis_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_delete_gbis"),
            "Targeted group": "Support to CWP eligible, gas and electricity",
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
            "Targeted group": "Support to CWP eligible, gas and electricity",
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
base_partial_whd_row = pd.DataFrame(
    [
        {
            "Levy reform": scenario_description.get("base_partial_whd"),
            "Targeted group": "Support to CWP eligible, gas and electricity",
            "WHD revenue (£ per year)": base_partial_whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": base_partial_whd_pc["whd"].revenue
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
                / base_partial_whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_gas
                / base_partial_whd_gas_tariff.calculate_variable_consumption(1)
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
        base_variable_whd_row,
        base_delete_gbis_row,
        base_delete_eco_row,
        base_partial_whd_row,
    ]
)

"""
Saving raw results data to Excel
"""
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_3_95pct.xlsx"

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
    f"{scenario_description.get('base_partial_whd')} + Unit discount on gas and electricity + False": "CORE - 2/3 WHD to tax - Ineligible",
    f"{scenario_description.get('base_partial_whd')} + Unit discount on gas and electricity + True": "CORE - 2/3 WHD to tax - Eligible",
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

"""
Saving Flourish data tables to Excel
"""
flourish_filename = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_3_95pct_flourish.xlsx"
)
try:
    with pd.ExcelWriter(flourish_filename, engine="xlsxwriter") as writer:
        # Master scenario tables
        master_summary_flourish.to_excel(
            writer, sheet_name="Master summary", index=False
        )
    print("Tables for Flourish successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")


"""
Pickling select dataframes for further processing
"""

pickle_path_summary = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_3_95pct_summary_table.pkl"
pickle_path_support_info = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_3_95pct_support_information.pkl"

try:
    master_summary_flourish.to_pickle(pickle_path_summary)
    support_info_df.to_pickle(pickle_path_support_info)
    print("Summary dataframes successfully pickled for further processing.")
except Exception as e:
    print(f"Failed to pickle dataframes: {e}")
