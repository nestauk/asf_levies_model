# %%
import asf_levies_model.levies as levies
import asf_levies_model.tariffs as tariffs
from asf_levies_model.consumers import Consumer, ConsumerCollection

import asf_levies_model.getters.load_data as data

from asf_levies_model.summary import create_scenario_weights_dict

# %%
# Denominator values from Desnz subnational consumption domestic data, 2023.
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

# %%
# Initialise levies
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


# %%
# Initialise tariffs (Other Payment method)
fileobject = data.download_annex_9(as_fileobject=True)

# Gas tariff
gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
)
# Electricity tariff
electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
)

fileobject.close()

# %%
# Rebalance initial levy denominators
pc = pc.rebalance_to_denominators()

# %% [markdown]
# ## Set 1 Scenarios - £450 flat rebate
#
# Fixed variables:
# Remove RO, FiT to gas.
# Warm Homes Discount 3x revenue (at baseline).
#
# Baseline:
# WHD eligible population.
#
# Vary:
# Eligibility:
# a) All pensioners.
# b) All Universal Credit
# c) All Child Benefit
# d) All pensioners + All Child Benefit.
#
# We want to maintain the rebate at £450, so we'll need to vary the revenue raised by WHD. As there isn't a 1:1 relationship between present WHD revenue and numbers eligible, we'll inflate the revenue based on the ratio whd elligible:test group eligible.
#

# %%
# Create the rebalanced baseline levies
rebalancing_weights = create_scenario_weights_dict(pc)

# update the ro and fit levies to gas.
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

# %%
# Rebalance policy costs; RO and FiT to gas.
pc = pc.rebalance_levies(rebalancing_weights, scenario_name="rebalance_ro_fit_to_gas")

# %%
# Increase the revenue collected by WHD to 3x
pc = pc.update_revenues({"whd": pc["whd"].revenue * 3})

# %%
# Update baseline bill policy costs to match rebalanced and revenue adjusted policy costs
gas_tariff = gas_tariff.update_policy_costs(pc)
electricity_tariff = electricity_tariff.update_policy_costs(pc)

# %%
# Create a ConsumerCollection for the baseline scenario
ofgem_archetypes_df = data.ofgem_archetypes_data()

# Create baseline consumers collection.
baseline_consumers = ConsumerCollection.from_dataframe(
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
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# %%
# Apply baseline WHD flat rate discount
baseline_consumers = baseline_consumers.apply_support_to_eligible_consumers(
    "electricity", -450, "flat adjustment", inplace=False
)

# %%
# Generate some conversion factors to create equivalent whd revenues for different eligibility groups.

# First load the eligibility data
# Load scheme eligibility size data
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()
# Load pensioners size data
ofgem_archetypes_retired_pension_df = data.ofgem_archetypes_retired_pension()
# Load benefit recipients size data
ofgem_archetypes_benefit_recipients_df = data.ofgem_archetypes_benefit_recipients()

# %%
# whd group is 4,709,573 people
# NB this is ~1m people more than you'd expect given the size of the WHD revenue.
total_whd_group = ofgem_archetypes_scheme_eligibility_df["WHDEligibleSize"].sum()

# %%
# pensioners group is 6,991,197
total_pensioners_group = ofgem_archetypes_retired_pension_df[
    "RetiredEconomicStatusSize"
].sum()

# %%
# UC group is 1,220,486
total_uc_group = ofgem_archetypes_benefit_recipients_df[
    "UniversalCreditRecipientSize"
].sum()

# %%
# Child benefit group is 6,368,447
total_child_benefit_group = ofgem_archetypes_benefit_recipients_df[
    "ChildBenefitRecipientSize"
].sum()

# %%
# Pensioners and child benefit group is 13,359,644
total_pensioners_child_benefit_group = (
    total_pensioners_group + total_child_benefit_group
)

# %% [markdown]
# ### Scenario 1a - All pensioners
# There are 1.48x more pensioners than whd eligible individuals, so we scale the WHD revenue to account for this.

# %%
# 1.484465152148613
# NB not using this as it appears to under estimate costs
whd_revenue_conversion_factor = 1 + (
    (total_pensioners_group - total_whd_group) / total_whd_group
)

# %%
whd_core_funding = 452_546_789
whd_recipients = 3_140_000
# revenue based on core funding amount and reported recipients
new_whd_revenue = (whd_core_funding / whd_recipients) * total_pensioners_group * 3

# %%
# Update whd revenue to account for eligible group size
pensioners_pc = pc.update_revenues({"whd": new_whd_revenue})

# %%
# total levy revenue ~£8.5bn
sum([levy.revenue for levy in pensioners_pc])

# %%
# Update baseline bill policy costs to match rebalanced and revenue adjusted policy costs
pensioner_gas_tariff = gas_tariff.update_policy_costs(pensioners_pc)
pensioner_electricity_tariff = electricity_tariff.update_policy_costs(pensioners_pc)

# %%
# Create pensioner consumers collection.
pensioner_consumers = ConsumerCollection.from_dataframe(
    collection_name="All pensioners scenario",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=pensioner_gas_tariff,
    electricity_tariff=pensioner_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# %%
# Apply WHD flat rate discount
pensioner_consumers = pensioner_consumers.apply_support_to_eligible_consumers(
    "electricity", -450, "flat adjustment", inplace=False
)

# %%


# %% [markdown]
# ### Scenario 1b - Universal Credit

# %%
# 0.2591500333469722
# Not using this as it doesn;t feel sufficiently accurate
whd_revenue_conversion_factor = 1 + (
    (total_uc_group - total_whd_group) / total_whd_group
)

# %%
whd_core_funding = 452_546_789
whd_recipients = 3_140_000
# revenue based on core funding amount and reported recipients
new_whd_revenue = (whd_core_funding / whd_recipients) * total_uc_group * 3

# %%
# Update whd revenue to account for eligible group size
uc_pc = pc.update_revenues({"whd": new_whd_revenue})

# %%
# total levy revenue ~£6bn
sum([levy.revenue for levy in uc_pc])

# %%
# Update baseline bill policy costs to match rebalanced and revenue adjusted policy costs
uc_gas_tariff = gas_tariff.update_policy_costs(uc_pc)
uc_electricity_tariff = electricity_tariff.update_policy_costs(uc_pc)

# %%
# Create pensioner consumers collection.
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

# %%
# Apply WHD flat rate discount
uc_consumers = uc_consumers.apply_support_to_eligible_consumers(
    "electricity", -450, "flat adjustment", inplace=False
)

# %%


# %% [markdown]
# ### Scenario 1c - Child Benefit

# %%
# 1.3522344807055757
# Not using as I think this leads to an underestimation of the revenue required.
whd_revenue_conversion_factor = 1 + (
    (total_child_benefit_group - total_whd_group) / total_whd_group
)

# %%
whd_core_funding = 452_546_789
whd_recipients = 3_140_000
# revenue based on core funding amount and reported recipients
new_whd_revenue = (whd_core_funding / whd_recipients) * total_child_benefit_group * 3

# %%
# Update whd revenue to account for eligible group size
child_benefit_pc = pc.update_revenues({"whd": new_whd_revenue})

# %%
# total levy revenue ~£8.2bn
sum([levy.revenue for levy in child_benefit_pc])

# %%
# Update baseline bill policy costs to match rebalanced and revenue adjusted policy costs
child_benefit_gas_tariff = gas_tariff.update_policy_costs(child_benefit_pc)
child_benefit_electricity_tariff = electricity_tariff.update_policy_costs(
    child_benefit_pc
)

# %%
# Create child benefit consumers collection.
child_benefit_consumers = ConsumerCollection.from_dataframe(
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
    gas_tariff=child_benefit_gas_tariff,
    electricity_tariff=child_benefit_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# %%


# %% [markdown]
# ### Child benefit and pensioner consumers

# %%
# Not using as I think this leads to an underestimation of the revenue required.
whd_revenue_conversion_factor = 1 + (
    (total_child_benefit_group - total_whd_group) / total_whd_group
)

# %%
