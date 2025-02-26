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
Defining support parameters
"""

whd_core_target_spending = pc["whd"].CoreSpending  # Annex 4
whd_noncore_target_spending = pc["whd"].NoncoreSpending
whd_core_target_recipients = whd_core_target_spending / 150

# whd_core_factor = 3

# core_target_spending_electricity_weight = 0.5
# core_target_spending_gas_weight = 0.5


"""
Loading eligibility size data
"""
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()
ofgem_archetypes_benefit_recipients_df = data.ofgem_archetypes_benefit_recipients()

total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()
total_wfp_group = ofgem_archetypes_scheme_eligibility_df["WFPEligibleSize"].sum()
total_cwp_group = ofgem_archetypes_scheme_eligibility_df["CWPEligibleSize"].sum()
total_uc_group = ofgem_archetypes_benefit_recipients_df[
    "UniversalCreditRecipientSize"
].sum()
total_cb_group = ofgem_archetypes_benefit_recipients_df[
    "ChildBenefitRecipientSize"
].sum()
total_wfp_cb_group = total_wfp_group + total_cb_group


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
Warm Homes Discount (WHD) eligibility
Levy reform: Rebalance RO and FiT to gas
Targeted support WHD eligible households
"""

# WHD eligibility sizes
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

# Estimate total electricity and gas consumption of all eligible households across archetypes
whd_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * scaled_whd_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers.iter_eligible()
)
whd_recipients_gas_consumption = sum(
    consumer.gas_consumption * scaled_whd_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers.iter_eligible()
)

# Portion WHD core spend for discounting electricity consumption and for discounting gas consumption
whd_core_target_spending_electricity_weight = whd_recipients_electricity_consumption / (
    whd_recipients_electricity_consumption + whd_recipients_gas_consumption
)
whd_core_target_spending_gas_weight = whd_recipients_gas_consumption / (
    whd_recipients_electricity_consumption + whd_recipients_gas_consumption
)

""" WHD revenue x1 """

whd_core_factor = 1

# Update revenue
whd_x1_pc = rebalanced_pc.update_revenues(
    {"whd": (whd_core_target_spending * whd_core_factor + whd_noncore_target_spending)}
)

# Update tariffs
whd_x1_gas_tariff = gas_tariff.update_policy_costs(whd_x1_pc)
whd_x1_electricity_tariff = electricity_tariff.update_policy_costs(whd_x1_pc)

# Create ConsumerCollection
whd_x1_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 1",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=whd_x1_gas_tariff,
    electricity_tariff=whd_x1_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)


# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
whd_x1_core_target_spending_electricity_dual = (
    whd_x1_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_electricity_weight
whd_x1_core_target_spending_gas_dual = (
    whd_x1_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_whd_x1_electricity_dual = (
    whd_x1_core_target_spending_electricity_dual
    / whd_recipients_electricity_consumption
)
unit_discount_whd_x1_gas_dual = (
    whd_x1_core_target_spending_gas_dual / whd_recipients_gas_consumption
)

# Apply support to eligible consumers
whd_x1_consumers_unit_discount_dual = (
    whd_x1_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_whd_x1_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_whd_x1_gas_dual, "unit discount", inplace=False
    )
)


""" WHD revenue x2 """

whd_core_factor = 2

# Update revenue
whd_x2_pc = rebalanced_pc.update_revenues(
    {"whd": (whd_core_target_spending * whd_core_factor + whd_noncore_target_spending)}
)

# Update tariffs
whd_x2_gas_tariff = gas_tariff.update_policy_costs(whd_x2_pc)
whd_x2_electricity_tariff = electricity_tariff.update_policy_costs(whd_x2_pc)

# Create ConsumerCollection
whd_x2_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 2",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=whd_x2_gas_tariff,
    electricity_tariff=whd_x2_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
whd_x2_core_target_spending_electricity_dual = (
    whd_x2_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_electricity_weight
whd_x2_core_target_spending_gas_dual = (
    whd_x2_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_whd_x2_electricity_dual = (
    whd_x2_core_target_spending_electricity_dual
    / whd_recipients_electricity_consumption
)
unit_discount_whd_x2_gas_dual = (
    whd_x2_core_target_spending_gas_dual / whd_recipients_gas_consumption
)

# Apply support to eligible consumers
whd_x2_consumers_unit_discount_dual = (
    whd_x2_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_whd_x2_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_whd_x2_gas_dual, "unit discount", inplace=False
    )
)

""" WHD revenue x3 """

whd_core_factor = 3

# Update revenue
whd_x3_pc = rebalanced_pc.update_revenues(
    {"whd": (whd_core_target_spending * whd_core_factor + whd_noncore_target_spending)}
)

# Update tariffs
whd_x3_gas_tariff = gas_tariff.update_policy_costs(whd_x3_pc)
whd_x3_electricity_tariff = electricity_tariff.update_policy_costs(whd_x3_pc)

# Create ConsumerCollection
whd_x3_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 3",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=whd_x3_gas_tariff,
    electricity_tariff=whd_x3_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
whd_x3_core_target_spending_electricity_dual = (
    whd_x3_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_electricity_weight
whd_x3_core_target_spending_gas_dual = (
    whd_x3_pc["whd"].revenue - whd_noncore_target_spending
) * whd_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_whd_x3_electricity_dual = (
    whd_x3_core_target_spending_electricity_dual
    / whd_recipients_electricity_consumption
)
unit_discount_whd_x3_gas_dual = (
    whd_x3_core_target_spending_gas_dual / whd_recipients_gas_consumption
)

# Apply support to eligible consumers
whd_x3_consumers_unit_discount_dual = (
    whd_x3_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_whd_x3_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_whd_x3_gas_dual, "unit discount", inplace=False
    )
)

"""
Cold Weather Payments (CWP) eligibility
Levy reform: Rebalance RO and FiT to gas
Targeted support CWP eligible households
"""

# CWP eligibility sizes
cwp_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="CWPEligibleSize",
)

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

""" WHD revenue x 1 x scaled to CWP """

whd_core_factor = 1

# Update revenue
cwp_x1_pc = rebalanced_pc.update_revenues(
    {
        "whd": (
            (total_cwp_group / whd_core_target_recipients)
            * (whd_core_target_spending * whd_core_factor)
            + whd_noncore_target_spending
        )
    }
)

# Update tariffs
cwp_x1_gas_tariff = gas_tariff.update_policy_costs(cwp_x1_pc)
cwp_x1_electricity_tariff = electricity_tariff.update_policy_costs(cwp_x1_pc)

# Create ConsumerCollection
cwp_x1_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 1 x scaled to CWP",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=cwp_x1_gas_tariff,
    electricity_tariff=cwp_x1_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
cwp_x1_core_target_spending_electricity_dual = (
    cwp_x1_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_electricity_weight
cwp_x1_core_target_spending_gas_dual = (
    cwp_x1_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_cwp_x1_electricity_dual = (
    cwp_x1_core_target_spending_electricity_dual
    / cwp_recipients_electricity_consumption
)
unit_discount_cwp_x1_gas_dual = (
    cwp_x1_core_target_spending_gas_dual / cwp_recipients_gas_consumption
)

# Apply support to eligible consumers
cwp_x1_consumers_unit_discount_dual = (
    cwp_x1_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_cwp_x1_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_cwp_x1_gas_dual, "unit discount", inplace=False
    )
)

""" WHD revenue x 2 x scaled to CWP """

whd_core_factor = 2

# Update revenue
cwp_x2_pc = rebalanced_pc.update_revenues(
    {
        "whd": (
            (total_cwp_group / whd_core_target_recipients)
            * (whd_core_target_spending * whd_core_factor)
            + whd_noncore_target_spending
        )
    }
)

# Update tariffs
cwp_x2_gas_tariff = gas_tariff.update_policy_costs(cwp_x2_pc)
cwp_x2_electricity_tariff = electricity_tariff.update_policy_costs(cwp_x2_pc)

# Create ConsumerCollection
cwp_x2_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 1 x scaled to CWP",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=cwp_x2_gas_tariff,
    electricity_tariff=cwp_x2_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
cwp_x2_core_target_spending_electricity_dual = (
    cwp_x2_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_electricity_weight
cwp_x2_core_target_spending_gas_dual = (
    cwp_x2_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_cwp_x2_electricity_dual = (
    cwp_x2_core_target_spending_electricity_dual
    / cwp_recipients_electricity_consumption
)
unit_discount_cwp_x2_gas_dual = (
    cwp_x2_core_target_spending_gas_dual / cwp_recipients_gas_consumption
)

# Apply support to eligible consumers
cwp_x2_consumers_unit_discount_dual = (
    cwp_x2_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_cwp_x2_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_cwp_x2_gas_dual, "unit discount", inplace=False
    )
)

""" WHD revenue x 3 x scaled to CWP """

whd_core_factor = 3

# Update revenue
cwp_x3_pc = rebalanced_pc.update_revenues(
    {
        "whd": (
            (total_cwp_group / whd_core_target_recipients)
            * (whd_core_target_spending * whd_core_factor)
            + whd_noncore_target_spending
        )
    }
)

# Update tariffs
cwp_x3_gas_tariff = gas_tariff.update_policy_costs(cwp_x3_pc)
cwp_x3_electricity_tariff = electricity_tariff.update_policy_costs(cwp_x3_pc)

# Create ConsumerCollection
cwp_x3_consumers = ConsumerCollection.from_dataframe(
    collection_name="Rebalance RO FiT on gas, WHD x 3 x scaled to CWP",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_95PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_95PCT",
    gas_tariff=cwp_x3_gas_tariff,
    electricity_tariff=cwp_x3_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity

# Allocate spending to electricity and gas discount
cwp_x3_core_target_spending_electricity_dual = (
    cwp_x3_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_electricity_weight
cwp_x3_core_target_spending_gas_dual = (
    cwp_x3_pc["whd"].revenue - whd_noncore_target_spending
) * cwp_core_target_spending_gas_weight

# Calculate unit discounts for electricity and gas
unit_discount_cwp_x3_electricity_dual = (
    cwp_x3_core_target_spending_electricity_dual
    / cwp_recipients_electricity_consumption
)
unit_discount_cwp_x3_gas_dual = (
    cwp_x3_core_target_spending_gas_dual / cwp_recipients_gas_consumption
)

# Apply support to eligible consumers
cwp_x3_consumers_unit_discount_dual = (
    cwp_x3_consumers.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_cwp_x3_electricity_dual,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_cwp_x3_gas_dual, "unit discount", inplace=False
    )
)

"""
Printing outputs
"""

# Information about levies
levy_collections = {
    pc: "Status quo",
    rebalanced_pc: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x1_pc: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x2_pc: "Rebalance RO+FiT to gas, WHD core revenue x 2",
    whd_x3_pc: "Rebalance RO+FiT to gas, WHD core revenue x 3",
    cwp_x1_pc: "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    cwp_x2_pc: "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    cwp_x3_pc: "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
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
    rebalanced_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    rebalanced_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x1_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x1_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x2_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 2",
    whd_x2_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 2",
    whd_x3_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 3",
    whd_x3_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 3",
    cwp_x1_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    cwp_x1_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    cwp_x2_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    cwp_x2_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    cwp_x3_gas_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
    cwp_x3_electricity_tariff: "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
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
    (
        rebalanced_electricity_tariff,
        rebalanced_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 1",
    (
        whd_x1_electricity_tariff,
        whd_x1_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 1",
    (
        whd_x2_electricity_tariff,
        whd_x2_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 2",
    (
        whd_x3_electricity_tariff,
        whd_x3_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 3",
    (
        cwp_x1_electricity_tariff,
        cwp_x1_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    (
        cwp_x2_electricity_tariff,
        cwp_x2_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    (
        cwp_x3_electricity_tariff,
        cwp_x3_gas_tariff,
    ): "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
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
    whd_x1_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 1",
    whd_x2_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 2",
    whd_x3_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 3",
    cwp_x1_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    cwp_x2_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    cwp_x3_consumers_unit_discount_dual: "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
}

consumer_collections_support_type = {
    status_quo_consumers_flat_rebate: "Flat rebate",
    rebalanced_consumers_flat_rebate: "Flat rebate",
    whd_x1_consumers_unit_discount_dual: "Unit discount gas and electricity",
    whd_x2_consumers_unit_discount_dual: "Unit discount gas and electricity",
    whd_x3_consumers_unit_discount_dual: "Unit discount gas and electricity",
    cwp_x1_consumers_unit_discount_dual: "Unit discount gas and electricity",
    cwp_x2_consumers_unit_discount_dual: "Unit discount gas and electricity",
    cwp_x3_consumers_unit_discount_dual: "Unit discount gas and electricity",
}

consumer_collections_eligibility = {
    status_quo_consumers_flat_rebate: "WHD",
    rebalanced_consumers_flat_rebate: "WHD",
    whd_x1_consumers_unit_discount_dual: "WHD",
    whd_x2_consumers_unit_discount_dual: "WHD",
    whd_x3_consumers_unit_discount_dual: "WHD",
    cwp_x1_consumers_unit_discount_dual: "CWP",
    cwp_x2_consumers_unit_discount_dual: "CWP",
    cwp_x3_consumers_unit_discount_dual: "CWP",
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
whd_x1_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 1",
            "Targeted group": "Support to WHD eligible, gas and electricity",
            "WHD revenue (£ per year)": whd_x1_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": whd_x1_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": whd_x1_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": whd_x1_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": whd_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": whd_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_whd_x1_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_whd_x1_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_whd_x1_electricity_dual
                / whd_x1_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_whd_x1_gas_dual
                / whd_x1_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
whd_x2_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 2",
            "Targeted group": "Support to WHD eligible, gas and electricity",
            "WHD revenue (£ per year)": whd_x2_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": whd_x2_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": whd_x2_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": whd_x2_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": whd_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": whd_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_whd_x2_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_whd_x2_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_whd_x2_electricity_dual
                / whd_x2_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_whd_x2_gas_dual
                / whd_x2_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
whd_x3_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 3",
            "Targeted group": "Support to WHD eligible, gas and electricity",
            "WHD revenue (£ per year)": whd_x3_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": whd_x3_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": whd_core_target_recipients,
            "WHD target spend on electricity consumption of target households (£)": whd_x3_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": whd_x3_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": whd_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": whd_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_whd_x3_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_whd_x3_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_whd_x3_electricity_dual
                / whd_x3_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_whd_x3_gas_dual
                / whd_x3_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
cwp_x1_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
            "Targeted group": "Support to CWP eligible, gas and electricity",
            "WHD revenue (£ per year)": cwp_x1_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": cwp_x1_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": cwp_x1_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": cwp_x1_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_cwp_x1_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_cwp_x1_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_cwp_x1_electricity_dual
                / cwp_x1_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_cwp_x1_gas_dual
                / cwp_x1_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
cwp_x2_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
            "Targeted group": "Support to CWP eligible, gas and electricity",
            "WHD revenue (£ per year)": cwp_x2_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": cwp_x2_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": cwp_x2_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": cwp_x2_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_cwp_x2_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_cwp_x2_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_cwp_x2_electricity_dual
                / cwp_x2_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_cwp_x2_gas_dual
                / cwp_x2_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
cwp_x3_dual_row = pd.DataFrame(
    [
        {
            "Levy reform": "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
            "Targeted group": "Support to CWP eligible, gas and electricity",
            "WHD revenue (£ per year)": cwp_x3_pc["whd"].revenue,
            "WHD target spend on core (£ per year)": cwp_x3_pc["whd"].revenue
            - whd_noncore_target_spending,
            "Number of target households": total_cwp_group,
            "WHD target spend on electricity consumption of target households (£)": cwp_x3_core_target_spending_electricity_dual,
            "WHD target spend on gas consumption of target households (£)": cwp_x3_core_target_spending_gas_dual,
            "Total electricity consumption of target households (MWh)": cwp_recipients_electricity_consumption,
            "Total gas consumption of target households (MWh)": cwp_recipients_gas_consumption,
            "Unit discount electricity (£/MWh)": unit_discount_cwp_x3_electricity_dual,
            "Unit discount gas (£/MWh)": unit_discount_cwp_x3_gas_dual,
            "Percentage discount on unit of electricity (%)": (
                unit_discount_cwp_x3_electricity_dual
                / cwp_x3_electricity_tariff.calculate_variable_consumption(1)
            )
            * 100,
            "Percentage discount on unit of gas (%)": (
                unit_discount_cwp_x3_gas_dual
                / cwp_x3_gas_tariff.calculate_variable_consumption(1)
            )
            * 100,
        }
    ]
)
support_info_df = pd.concat(
    [
        support_info_df,
        rebalanced_row,
        whd_x1_dual_row,
        whd_x2_dual_row,
        whd_x3_dual_row,
        cwp_x1_dual_row,
        cwp_x2_dual_row,
        cwp_x3_dual_row,
    ]
)

"""
Saving raw results data to Excel
"""
today = datetime.now()
date_str = today.strftime("%Y%m%d")
filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct.xlsx"

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
scenario_description = {
    "Status quo, WHD revenue x 1 + Flat rebate + False": "Status quo - WHD - Flat rebate - Ineligible",
    "Status quo, WHD revenue x 1 + Flat rebate + True": "Status quo - WHD - Flat rebate - Eligible",
    "Rebalance RO+FiT to gas, WHD revenue x 1 + Flat rebate + False": "Rebalancing - WHD - Flat rebate - Ineligible",
    "Rebalance RO+FiT to gas, WHD revenue x 1 + Flat rebate + True": "Rebalancing - WHD - Flat rebate - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 1 + Unit discount gas and electricity + False": "Rebalancing - WHD - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 1 + Unit discount gas and electricity + True": "Rebalancing - WHD - Unit discount - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 2 + Unit discount gas and electricity + False": "Rebalancing - WHDx2 - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 2 + Unit discount gas and electricity + True": "Rebalancing - WHDx2 - Unit discount - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 3 + Unit discount gas and electricity + False": "Rebalancing - WHDx3 - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 3 + Unit discount gas and electricity + True": "Rebalancing - WHDx3 - Unit discount - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP + Unit discount gas and electricity + False": "Rebalancing - CWP - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP + Unit discount gas and electricity + True": "Rebalancing - CWP - Unit discount - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP + Unit discount gas and electricity + False": "Rebalancing - CWPx2 - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP + Unit discount gas and electricity + True": "Rebalancing - CWPx2 - Unit discount - Eligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP + Unit discount gas and electricity + False": "Rebalancing - CWPx3 - Unit discount - Ineligible",
    "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP + Unit discount gas and electricity + True": "Rebalancing - CWPx3 - Unit discount - Eligible",
}
master_summary_flourish["ScenarioLabel"] = master_summary_flourish[
    "ScenarioSupportEligibility"
].map(scenario_description)

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

# Specify order
scenario_order = [
    "Status quo, WHD revenue x 1",
    "Rebalance RO+FiT to gas, WHD revenue x 1",
    "Rebalance RO+FiT to gas, WHD core revenue x 1",
    "Rebalance RO+FiT to gas, WHD core revenue x 2",
    "Rebalance RO+FiT to gas, WHD core revenue x 3",
    "Rebalance RO+FiT to gas, WHD core revenue x 1 x scaled to CWP",
    "Rebalance RO+FiT to gas, WHD core revenue x 2 x scaled to CWP",
    "Rebalance RO+FiT to gas, WHD core revenue x 3 x scaled to CWP",
]
master_summary_flourish = (
    master_summary_flourish.assign(
        ScenarioRank=master_summary_flourish["Scenario"].map(
            {s: i for i, s in enumerate(scenario_order)}
        )
    )
    .sort_values(["ScenarioRank", "Name", "SupportType", "EligibleForSupport"])
    .drop(columns=["ScenarioRank"])
    .reset_index(drop=True)
)

"""
Saving Flourish data tables to Excel
"""
flourish_filename = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct_flourish.xlsx"
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

pickle_path_summary = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct_summary_table.pkl"
pickle_path_support_info = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct_support_information.pkl"

try:
    master_summary_flourish.to_pickle(pickle_path_summary)
    support_info_df.to_pickle(pickle_path_support_info)
    print("Summary dataframes successfully pickled for further processing.")
except Exception as e:
    print(f"Failed to pickle dataframes: {e}")
