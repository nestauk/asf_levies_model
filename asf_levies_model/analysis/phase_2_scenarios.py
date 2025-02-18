import pandas as pd
from datetime import datetime
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
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

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
    levies.ECO.from_dataframe(data.process_data_ECO(fileobject)),
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
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
Setting up status quo Consumers
"""
# Create a rebalanced with status quo WHD rebate ConsumerCollection
ofgem_archetypes_df = data.ofgem_archetypes_data()
status_quo_consumers = ConsumerCollection.from_dataframe(
    collection_name="Baseline RO FiT on gas WHDx1",
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
Rebalance levies
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
    collection_name="Baseline RO FiT on gas WHDx1",
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
Defining support parameters
"""
flat_rebate = -450
whd_core_target_spending = 452_546_789  # Annex 4
whd_core_target_recipients = whd_core_target_spending / 150

whd_core_share = whd_core_target_spending / pc["whd"].revenue

core_target_spending_electricity_weight = 0.5
core_target_spending_gas_weight = 0.5


"""
Loading eligibility size data
"""
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()
ofgem_archetypes_benefit_recipients_df = data.ofgem_archetypes_benefit_recipients()

total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()
total_wfp_group = ofgem_archetypes_scheme_eligibility_df["WFPEligibleSize"].sum()
total_uc_group = ofgem_archetypes_benefit_recipients_df[
    "UniversalCreditRecipientSize"
].sum()
total_cb_group = ofgem_archetypes_benefit_recipients_df[
    "ChildBenefitRecipientSize"
].sum()
total_wfp_cb_group = total_wfp_group + total_cb_group


"""
0. Baseline Warm Homes Discount (WHD) eligibility
Levy reform: Rebalance RO and FiT to gas, Warm Homes Discount 3x revenue
Targeted support: WHD eligible households
"""

# Increase WHD revenue
whd_pc = rebalanced_pc.update_revenues({"whd": pc["whd"].revenue * 3})

# Update tariffs
whd_gas_tariff = gas_tariff.update_policy_costs(whd_pc)
whd_electricity_tariff = electricity_tariff.update_policy_costs(whd_pc)

# Create a triple WHD ConsumerCollection
whd_consumers = ConsumerCollection.from_dataframe(
    collection_name="Baseline RO FiT on gas WHDx3",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=whd_gas_tariff,
    electricity_tariff=whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Support method 1: Flat rebate discount

# Apply support to eligible consumers
whd_consumers_flat_rebate = whd_consumers.apply_support_to_eligible_consumers(
    "electricity", flat_rebate, "flat adjustment", inplace=False
)

# Support method 2: Unit discount

# Get eligible group sizes for each archetype
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

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
whd_core_target_spending_electricity = (
    whd_pc["whd"].revenue * whd_core_share * core_target_spending_electricity_weight
)
whd_core_target_spending_gas = (
    whd_pc["whd"].revenue * whd_core_share * core_target_spending_gas_weight
)

# Estimate total electricity and gas consumption of all eligible households across archetypes
whd_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * scaled_whd_sizes[consumer.archetype][True]
    for consumer in whd_consumers.iter_eligible()
)
whd_recipients_gas_consumption = sum(
    consumer.gas_consumption * scaled_whd_sizes[consumer.archetype][True]
    for consumer in whd_consumers.iter_eligible()
)

# Calculate unit discounts for electricity and gas
unit_discount_whd_electricity = (
    whd_core_target_spending_electricity / whd_recipients_electricity_consumption
)
unit_discount_whd_gas = whd_core_target_spending_gas / whd_recipients_gas_consumption

# Apply support to eligible consumers
whd_consumers_unit_discount = whd_consumers.apply_support_to_eligible_consumers(
    "electricity", unit_discount_whd_electricity, "unit discount", inplace=False
).apply_support_to_eligible_consumers(
    "gas", unit_discount_whd_gas, "unit discount", inplace=False
)


"""
A. Winter Fuel Payment (WFP) eligibility
Levy reform: Rebalance RO and FiT to gas, Warm Homes Discount 3x revenue scaled to WFP eligibility size
Targeted support: WFP eligible households
"""

# Increase WHD revenue
wfp_pc = rebalanced_pc.update_revenues(
    {"whd": (total_wfp_group / whd_core_target_recipients) * (pc["whd"].revenue * 3)}
)

# Update tariffs
wfp_gas_tariff = gas_tariff.update_policy_costs(wfp_pc)
wfp_electricity_tariff = electricity_tariff.update_policy_costs(wfp_pc)

# Create a WFP ConsumerCollection
wfp_consumers = ConsumerCollection.from_dataframe(
    collection_name="All WFP scenario",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=wfp_gas_tariff,
    electricity_tariff=wfp_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Support method 1: Flat rebate discount

# Apply support to eligible consumers
wfp_consumers_flat_rebate = wfp_consumers.apply_support_to_eligible_consumers(
    "electricity", flat_rebate, "flat adjustment", inplace=False
)

# Support method 2: Unit discount

# Set new target core spend for WFP eligible households' electricity and gas consumption
wfp_core_target_spending_electricity = (
    wfp_pc["whd"].revenue * whd_core_share * core_target_spending_electricity_weight
)
wfp_core_target_spending_gas = (
    wfp_pc["whd"].revenue * whd_core_share * core_target_spending_gas_weight
)

# Get eligible group sizes for each archetype
wfp_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="WFPEligibleSize",
)

# Estimate total electricity and gas consumption of all eligible households across archetypes
wfp_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * wfp_sizes[consumer.archetype][True]
    for consumer in wfp_consumers.iter_eligible()
)
wfp_recipients_gas_consumption = sum(
    consumer.gas_consumption * wfp_sizes[consumer.archetype][True]
    for consumer in wfp_consumers.iter_eligible()
)

# Calculate unit discounts for electricity and gas
unit_discount_wfp_electricity = (
    wfp_core_target_spending_electricity / wfp_recipients_electricity_consumption
)
unit_discount_wfp_gas = wfp_core_target_spending_gas / wfp_recipients_gas_consumption

# Apply support to eligible consumers
wfp_consumers_unit_discount = wfp_consumers.apply_support_to_eligible_consumers(
    "electricity", unit_discount_wfp_electricity, "unit discount", inplace=False
).apply_support_to_eligible_consumers(
    "gas", unit_discount_wfp_gas, "unit discount", inplace=False
)


"""
B. Universal Credit (UC) recipient eligibility
Levy reform: Rebalance RO and FiT to gas, Warm Homes Discount 3x revenue scaled to UC recipient size
Targeted support: UC recipient households
"""

# Increase WHD revenue
uc_pc = rebalanced_pc.update_revenues(
    {"whd": (total_uc_group / whd_core_target_recipients) * (pc["whd"].revenue * 3)}
)

# Update tariffs
uc_gas_tariff = gas_tariff.update_policy_costs(uc_pc)
uc_electricity_tariff = electricity_tariff.update_policy_costs(uc_pc)

# Create a UC ConsumerCollection
uc_consumers = ConsumerCollection.from_dataframe(
    collection_name="All Universal Credit scenario",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=uc_gas_tariff,
    electricity_tariff=uc_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Support method 1: Flat rebate discount

# Apply support to eligible consumers
uc_consumers_flat_rebate = uc_consumers.apply_support_to_eligible_consumers(
    "electricity", flat_rebate, "flat adjustment", inplace=False
)

# Support method 2: Unit discount

# Set new target core spend for UC recipient households' electricity and gas consumption
uc_core_target_spending_electricity = (
    uc_pc["whd"].revenue * whd_core_share * core_target_spending_electricity_weight
)
uc_core_target_spending_gas = (
    uc_pc["whd"].revenue * whd_core_share * core_target_spending_gas_weight
)

# Get eligible group sizes for each archetype
uc_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_benefit_recipients_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="UniversalCreditRecipientSize",
)

# Estimate total electricity and gas consumption of all eligible households across archetypes
uc_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * uc_sizes[consumer.archetype][True]
    for consumer in uc_consumers.iter_eligible()
)
uc_recipients_gas_consumption = sum(
    consumer.gas_consumption * uc_sizes[consumer.archetype][True]
    for consumer in uc_consumers.iter_eligible()
)

# Calculate unit discounts for electricity and gas
unit_discount_uc_electricity = (
    uc_core_target_spending_electricity / uc_recipients_electricity_consumption
)
unit_discount_uc_gas = uc_core_target_spending_gas / uc_recipients_gas_consumption

# Apply support to eligible consumers
uc_consumers_unit_discount = uc_consumers.apply_support_to_eligible_consumers(
    "electricity", unit_discount_uc_electricity, "unit discount", inplace=False
).apply_support_to_eligible_consumers(
    "gas", unit_discount_uc_gas, "unit discount", inplace=False
)


"""
C. Child Benefit (CB) recipient eligibility
Levy reform: Rebalance RO and FiT to gas, Warm Homes Discount 3x revenue scaled to CB recipient size
Targeted support: CB recipient eligible households
"""

# Increase WHD revenue
cb_pc = rebalanced_pc.update_revenues(
    {"whd": (total_cb_group / whd_core_target_recipients) * (pc["whd"].revenue * 3)}
)

# Update tariffs
cb_gas_tariff = gas_tariff.update_policy_costs(cb_pc)
cb_electricity_tariff = electricity_tariff.update_policy_costs(cb_pc)

# Create a CB ConsumerCollection
cb_consumers = ConsumerCollection.from_dataframe(
    collection_name="All Universal Credit scenario",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=cb_gas_tariff,
    electricity_tariff=cb_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Support method 1: Flat rebate discount

# Apply support to eligible consumers
cb_consumers_flat_rebate = cb_consumers.apply_support_to_eligible_consumers(
    "electricity", flat_rebate, "flat adjustment", inplace=False
)

# Support method 2: Unit discount

# Set new target core spend for CB recipient households' electricity and gas consumption
cb_core_target_spending_electricity = (
    cb_pc["whd"].revenue * whd_core_share * core_target_spending_electricity_weight
)
cb_core_target_spending_gas = (
    cb_pc["whd"].revenue * whd_core_share * core_target_spending_gas_weight
)

# Get eligible group sizes for each archetype
cb_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_benefit_recipients_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="ChildBenefitRecipientSize",
)

# Estimate total electricity and gas consumption of all eligible households across archetypes
cb_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * cb_sizes[consumer.archetype][True]
    for consumer in cb_consumers.iter_eligible()
)
cb_recipients_gas_consumption = sum(
    consumer.gas_consumption * cb_sizes[consumer.archetype][True]
    for consumer in cb_consumers.iter_eligible()
)

# Calculate unit discounts for electricity and gas
unit_discount_cb_electricity = (
    cb_core_target_spending_electricity / cb_recipients_electricity_consumption
)
unit_discount_cb_gas = cb_core_target_spending_gas / cb_recipients_gas_consumption

# Apply support to eligible consumers
cb_consumers_unit_discount = cb_consumers.apply_support_to_eligible_consumers(
    "electricity", unit_discount_cb_electricity, "unit discount", inplace=False
).apply_support_to_eligible_consumers(
    "gas", unit_discount_cb_gas, "unit discount", inplace=False
)


"""
D. Winter Fuel Payment (WFP) & Child Benefit (CB) recipient eligibility
Levy reform: Rebalance RO and FiT to gas, Warm Homes Discount 3x revenue scaled to WFP+CB eligibility/recipient size
Targeted support: WFP+CB eligible/recipient households
"""

# Increase WHD revenue
wfp_cb_pc = rebalanced_pc.update_revenues(
    {"whd": (total_wfp_cb_group / whd_core_target_recipients) * (pc["whd"].revenue * 3)}
)

# Update tariffs
wfp_cb_gas_tariff = gas_tariff.update_policy_costs(wfp_cb_pc)
wfp_cb_electricity_tariff = electricity_tariff.update_policy_costs(wfp_cb_pc)

# Create a WFP+CB ConsumerCollection
wfp_cb_consumers = ConsumerCollection.from_dataframe(
    collection_name="All Universal Credit scenario",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=wfp_cb_gas_tariff,
    electricity_tariff=wfp_cb_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Support method 1: Flat rebate discount

# Apply support to eligible consumers
wfp_cb_consumers_flat_rebate = wfp_cb_consumers.apply_support_to_eligible_consumers(
    "electricity", flat_rebate, "flat adjustment", inplace=False
)

# Support method 2: Unit discount

# Set new target core spend for WFP+CB recipient households' electricity and gas consumption
wfp_cb_core_target_spending_electricity = (
    wfp_cb_pc["whd"].revenue * whd_core_share * core_target_spending_electricity_weight
)
wfp_cb_core_target_spending_gas = (
    wfp_cb_pc["whd"].revenue * whd_core_share * core_target_spending_gas_weight
)

# Get eligible group sizes for each archetype
wfp_cb_sizes = {
    key: {
        True: wfp_sizes[key][True] + cb_sizes[key][True],
        False: wfp_sizes[key][False] + cb_sizes[key][False],
    }
    for key in wfp_sizes
    if key in cb_sizes
}

# Estimate total electricity and gas consumption of all eligible households across archetypes
wfp_cb_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * wfp_cb_sizes[consumer.archetype][True]
    for consumer in wfp_cb_consumers.iter_eligible()
)
wfp_cb_recipients_gas_consumption = sum(
    consumer.gas_consumption * wfp_cb_sizes[consumer.archetype][True]
    for consumer in wfp_cb_consumers.iter_eligible()
)

# Calculate unit discounts for electricity and gas
unit_discount_wfp_cb_electricity = (
    wfp_cb_core_target_spending_electricity / wfp_cb_recipients_electricity_consumption
)
unit_discount_wfp_cb_gas = (
    wfp_cb_core_target_spending_gas / wfp_cb_recipients_gas_consumption
)

# Apply support to eligible consumers
wfp_cb_consumers_unit_discount = wfp_cb_consumers.apply_support_to_eligible_consumers(
    "electricity", unit_discount_wfp_cb_electricity, "unit discount", inplace=False
).apply_support_to_eligible_consumers(
    "gas", unit_discount_wfp_cb_gas, "unit discount", inplace=False
)

"""
Printing outputs
"""

# Information about levies
levy_collections = {
    pc: "Status quo",
    rebalanced_pc: "Rebalance RO+FiT to gas",
    whd_pc: "Rebalance RO+FiT to gas; WHD revenue x 3",
    wfp_pc: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    uc_pc: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    cb_pc: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    wfp_cb_pc: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
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
    gas_tariff: "Status quo",
    electricity_tariff: "Status quo",
    rebalanced_gas_tariff: "Rebalance RO+FiT to gas",
    rebalanced_electricity_tariff: "Rebalance RO+FiT to gas",
    whd_gas_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3",
    whd_electricity_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3",
    wfp_gas_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    wfp_electricity_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    uc_gas_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    uc_electricity_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    cb_gas_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    cb_electricity_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    wfp_cb_gas_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
    wfp_cb_electricity_tariff: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
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
    (electricity_tariff, gas_tariff): "Status quo",
    (rebalanced_electricity_tariff, rebalanced_gas_tariff): "Rebalance RO+FiT to gas",
    (
        whd_electricity_tariff,
        whd_gas_tariff,
    ): "Rebalance RO+FiT to gas; WHD revenue x 3",
    (
        wfp_electricity_tariff,
        wfp_gas_tariff,
    ): "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    (
        uc_electricity_tariff,
        uc_gas_tariff,
    ): "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    (
        cb_electricity_tariff,
        cb_gas_tariff,
    ): "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    (
        wfp_cb_electricity_tariff,
        wfp_cb_gas_tariff,
    ): "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
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
    status_quo_consumers_flat_rebate: "Status quo, WHD revenue x 1",
    rebalanced_consumers_flat_rebate: "Rebalance RO+FiT to gas, WHD revenue x 1",
    whd_consumers_flat_rebate: "Rebalance RO+FiT to gas; WHD revenue x 3",
    whd_consumers_unit_discount: "Rebalance RO+FiT to gas; WHD revenue x 3",
    wfp_consumers_flat_rebate: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    wfp_consumers_unit_discount: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    uc_consumers_flat_rebate: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    uc_consumers_unit_discount: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    cb_consumers_flat_rebate: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    cb_consumers_unit_discount: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    wfp_cb_consumers_flat_rebate: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
    wfp_cb_consumers_unit_discount: "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
}

consumer_collections_support_type = {
    status_quo_consumers_flat_rebate: "Flat rebate",
    rebalanced_consumers_flat_rebate: "Flat rebate",
    whd_consumers_flat_rebate: "Flat rebate",
    whd_consumers_unit_discount: "Unit discount",
    wfp_consumers_flat_rebate: "Flat rebate",
    wfp_consumers_unit_discount: "Unit discount",
    uc_consumers_flat_rebate: "Flat rebate",
    uc_consumers_unit_discount: "Unit discount",
    cb_consumers_flat_rebate: "Flat rebate",
    cb_consumers_unit_discount: "Unit discount",
    wfp_cb_consumers_flat_rebate: "Flat rebate",
    wfp_cb_consumers_unit_discount: "Unit discount",
}

consumer_collections_eligibility = {
    status_quo_consumers_flat_rebate: "WHD",
    rebalanced_consumers_flat_rebate: "WHD",
    whd_consumers_flat_rebate: "WHD",
    whd_consumers_unit_discount: "WHD",
    wfp_consumers_flat_rebate: "WFP",
    wfp_consumers_unit_discount: "WFP",
    uc_consumers_flat_rebate: "UC",
    uc_consumers_unit_discount: "UC",
    cb_consumers_flat_rebate: "CB",
    cb_consumers_unit_discount: "CB",
    wfp_cb_consumers_flat_rebate: "WFP+CB",
    wfp_cb_consumers_unit_discount: "WFP+CB",
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
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 1",
            "Targeted group": "Support to WHD eligible",
            "WHD revenue (£ per year)": rebalanced_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": whd_core_target_spending,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": None,
            "WHD target spend on gas consumption of target households (£)": None,
            "Total electricity consumption of target households (MWh)": None,
            "Total gas consumption of target households (MWh)": None,
            "Flat rebate (£)": 150,
        }
    ]
)
whd_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 3",
            "Targeted group": "Support to WHD eligible",
            "WHD revenue (£ per year)": whd_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": whd_pc["whd"].revenue
            * whd_core_share,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": whd_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": whd_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": whd_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": whd_recipients_gas_consumption,
            "Flat rebate (£)": 450,
            "Unit discount electricity (£/MWh)": unit_discount_whd_electricity,
            "Unit discount gas (£/MWh)": unit_discount_whd_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_whd_electricity
                / whd_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_whd_gas / whd_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
wfp_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 3 x scaled to WFP eligibility size",
            "Targeted group": "Support to WFP eligible",
            "WHD revenue (£ per year)": wfp_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": wfp_pc["whd"].revenue
            * whd_core_share,
            "Number of target households": total_wfp_group,
            "WHD target spend on electricity consumption of target households (£)": wfp_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": wfp_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": wfp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": wfp_recipients_gas_consumption,
            "Flat rebate (£)": 450,
            "Unit discount electricity (£/MWh)": unit_discount_wfp_electricity,
            "Unit discount gas (£/MWh)": unit_discount_wfp_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_wfp_electricity
                / wfp_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_wfp_gas / wfp_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
uc_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 3 x scaled to UC eligibility size",
            "Targeted group": "Support to Universal Credit recipients",
            "WHD revenue (£ per year)": uc_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": uc_pc["whd"].revenue
            * whd_core_share,
            "Number of target households": total_uc_group,
            "WHD target spend on electricity consumption of target households (£)": uc_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": uc_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": uc_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": uc_recipients_gas_consumption,
            "Flat rebate (£)": 450,
            "Unit discount electricity (£/MWh)": unit_discount_uc_electricity,
            "Unit discount gas (£/MWh)": unit_discount_uc_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_uc_electricity
                / uc_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_uc_gas / uc_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
cb_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 3 x scaled to CB eligibility size",
            "Targeted group": "Support to Child Benefit recipients",
            "WHD revenue (£ per year)": cb_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": cb_pc["whd"].revenue
            * whd_core_share,
            "Number of target households": total_cb_group,
            "WHD target spend on electricity consumption of target households (£)": cb_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": cb_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": cb_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cb_recipients_gas_consumption,
            "Flat rebate (£)": 450,
            "Unit discount electricity (£/MWh)": unit_discount_cb_electricity,
            "Unit discount gas (£/MWh)": unit_discount_cb_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_cb_electricity
                / cb_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_cb_gas / cb_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
wfp_cb_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FIT to gas, WHD revenue x 3 x scaled to WFP+CB eligibility size",
            "Targeted group": "Support to Winter Fuel Payment and Child Benefit eligible/recipient households",
            "WHD revenue (£ per year)": wfp_cb_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": wfp_cb_pc["whd"].revenue
            * whd_core_share,
            "Number of target households": total_wfp_cb_group,
            "WHD target spend on electricity consumption of target households (£)": wfp_cb_core_target_spending_electricity,
            "WHD target spend on gas consumption of target households (£)": wfp_cb_core_target_spending_gas,
            "Total electricity consumption of target households (MWh)": wfp_cb_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": wfp_cb_recipients_gas_consumption,
            "Flat rebate (£)": 450,
            "Unit discount electricity (£/MWh)": unit_discount_wfp_cb_electricity,
            "Unit discount gas (£/MWh)": unit_discount_wfp_cb_gas,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_wfp_cb_electricity
                / wfp_cb_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_wfp_cb_gas
                / wfp_cb_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)

support_info_df = pd.concat(
    [support_info_df, rebalanced_row, whd_row, wfp_row, uc_row, cb_row, wfp_cb_row]
)


"""
Saving raw results data to Excel
"""
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios.xlsx"

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

# Add group sizes
eligibility_size_lookup = {
    "WHD": scaled_whd_sizes,
    "WFP": wfp_sizes,
    "UC": uc_sizes,
    "CB": cb_sizes,
    "WFP+CB": wfp_cb_sizes,
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
archetype_sizes = ofgem_archetypes_benefit_recipients_df[
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
baseline_scenario = "Status quo, WHD revenue x 1 + Flat rebate"

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

scenario_order = [
    "Status quo, WHD revenue x 1",
    "Rebalance RO+FiT to gas, WHD revenue x 1",
    "Rebalance RO+FiT to gas; WHD revenue x 3",
    "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP eligibility size",
    "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to UC eligibility size",
    "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to CB eligibility size",
    "Rebalance RO+FiT to gas; WHD revenue x 3 x scaled to WFP+CB eligibility size",
]
master_summary_flourish = (
    master_summary_flourish.assign(
        ScenarioRank=master_summary_flourish["Scenario"].map(
            {s: i for i, s in enumerate(scenario_order)}
        )
    )
    .sort_values(["ScenarioRank", "Name", "EligibleForSupport"])
    .drop(columns=["ScenarioRank"])  # Drop the temporary ranking column
    .reset_index(drop=True)
)


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
    arrow_rows["Net change in annual energy bill"] = (
        arrow_rows["Net change in annual energy bill"] + 10
    )
    arrow_rows["Group"] = arrow_rows["Group"].str.replace("b", "")
    table = pd.concat([table, arrow_rows], ignore_index=True)

    return table


# List of unique levy reform and support scenarios
unique_scenarios = master_summary_flourish["ScenarioSupport"].unique().tolist()
unique_scenarios.remove("Status quo, WHD revenue x 1 + Flat rebate")

# Create table for Flourish chart for each scenario
scenario_tables = {}
for scenario in unique_scenarios:
    scenario_table = create_table_for_flourish(master_summary_flourish, scenario)
    scenario_tables[scenario] = scenario_table


"""
Saving Flourish data tables to Excel
"""
flourish_filename = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_flourish.xlsx"
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
