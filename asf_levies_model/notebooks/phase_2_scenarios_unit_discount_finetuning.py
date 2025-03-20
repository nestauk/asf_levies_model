# %%
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

# %%
import warnings

warnings.simplefilter("ignore")

# %% [markdown]
# ### General set up

# %%
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

# %% [markdown]
# ### Setting up mean and median status quo consumers

# %%
ofgem_archetypes_df = data.ofgem_archetypes_data()
ofgem_archetypes_scheme_eligibility_df = data.ofgem_archetypes_scheme_eligibility()

# %%
# Mean consumption
status_quo_consumers_mean = ConsumerCollection.from_dataframe(
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

status_quo_consumers_flat_rebate_mean = (
    status_quo_consumers_mean.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)

# %%
# Median consumption
lookup_50pct = (
    ofgem_archetypes_df.loc[
        lambda df: df["AnnualConsumptionProfile"].isin(
            [
                "A1_50PCT",
                "A2_50PCT",
                "A3_50PCT",
                "B4_50PCT",
                "B5_50PCT",
                "B6_50PCT",
                "C7_50PCT",
                "C8_50PCT",
                "C9_50PCT",
                "D10_50PCT",
                "D11_50PCT",
                "D12_50PCT",
                "E13_50PCT",
                "E14_50PCT",
                "F15_50PCT",
                "F16_50PCT",
                "G17_50PCT",
                "G18_50PCT",
                "H19_50PCT",
                "H20_50PCT",
                "I21_50PCT",
                "I22_50PCT",
                "J23_50PCT",
                "J24_50PCT",
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
            "ElectricitySingleRatekWh": "ElectricitySingleRatekWh_50PCT",
            "GaskWh": "GaskWh_50PCT",
        }
    )
)
# Merge lookup_50pct with ofgem_archetypes_df
ofgem_archetypes_df = ofgem_archetypes_df.merge(
    lookup_50pct, how="left", on="AnnualConsumptionProfile"
)

status_quo_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="Status quo",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

status_quo_consumers_flat_rebate_median = (
    status_quo_consumers_median.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)

# %%
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers("mean"),
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers("median"),
    ]
)

master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == "mean")
        & (master_summary_flourish["EligibleForSupport"] == row.EligibleForSupport),
        "combined_fuel_bill",
    ].values
    # Ensure a baseline bill exists before subtracting
    baseline_bill = baseline_bill[0] if len(baseline_bill) > 0 else None
    # Compute the bill change or assign NaN if no baseline bill found
    bill_changes.append(
        row.combined_fuel_bill - baseline_bill if baseline_bill is not None else None
    )
master_summary_flourish.loc[:, "Change in bill wrt mean"] = bill_changes

df = master_summary_flourish[master_summary_flourish["Scenario"] == "median"]

# %%
df

# %% [markdown]
# ### Comparing mean and median rebalanced consumers

# %%
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

# %% [markdown]
# Mean

# %%
# Create a rebalanced with status quo WHD rebate ConsumerCollection
rebalanced_consumers_mean = ConsumerCollection.from_dataframe(
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
rebalanced_consumers_flat_rebate_mean = (
    rebalanced_consumers_mean.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Rebalanced mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        rebalanced_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]

archetype_sizes = ofgem_archetypes_scheme_eligibility_df[
    ["AnnualConsumptionProfile", "ArchetypeSize"]
]
archetype_sizes = archetype_sizes.rename(
    columns={
        "AnnualConsumptionProfile": "Name",
    }
)
df = df.merge(archetype_sizes, on="Name", how="left")

# %%
# What is the range of bill change for gas-using households?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# Which archetype has the highest bill change to mitigate?
df.loc[df["Net change in annual energy bill"].idxmax()]

# %%
# What is the weighted average bill change for gas-using households?
filtered_df = df[(df["main_heating_fuel"] == "Gas")]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["ArchetypeSize"]
).sum() / filtered_df["ArchetypeSize"].sum()

# %%
# What is the WHD revenue?
print(str(pc["whd"].revenue / 1e9), "billion")

# %% [markdown]
# Median

# %%
# Create a rebalanced with status quo WHD rebate ConsumerCollection
rebalanced_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="Baseline RO FiT on gas, WHD x 1",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=rebalanced_gas_tariff,
    electricity_tariff=rebalanced_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=False,
)

# Apply status quo £150 WHD rebate
rebalanced_consumers_flat_rebate_median = (
    rebalanced_consumers_median.apply_support_to_eligible_consumers(
        "electricity", -150, "flat adjustment", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Rebalanced median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        rebalanced_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]

archetype_sizes = ofgem_archetypes_scheme_eligibility_df[
    ["AnnualConsumptionProfile", "ArchetypeSize"]
]
archetype_sizes = archetype_sizes.rename(
    columns={
        "AnnualConsumptionProfile": "Name",
    }
)
df = df.merge(archetype_sizes, on="Name", how="left")

# %%
# What is the range of bill change for gas-using households?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# Which archetype has the highest bill change to mitigate?
df.loc[df["Net change in annual energy bill"].idxmax()]

# %%
# What is the weighted average bill change for gas-using households?
filtered_df = df[(df["main_heating_fuel"] == "Gas")]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["ArchetypeSize"]
).sum() / filtered_df["ArchetypeSize"].sum()

# %%
# What is the WHD revenue?
print(str(pc["whd"].revenue / 1e9), "billion")

# %% [markdown]
# ### Universal parameters

# %%
# Load CWP sizes
total_cwp_group = ofgem_archetypes_scheme_eligibility_df["CWPEligibleSize"].sum()

cwp_sizes = create_eligibility_group_sizes_dictionary(
    df=ofgem_archetypes_scheme_eligibility_df,
    group_name_col="AnnualConsumptionProfile",
    total_size_col="ArchetypeSize",
    eligible_size_col="CWPEligibleSize",
)

# %%
# Estimate total electricity and gas consumption of all eligible households across archetypes
cwp_recipients_electricity_consumption = sum(
    consumer.electricity_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers_mean.iter_eligible()
)
cwp_recipients_gas_consumption = sum(
    consumer.gas_consumption * cwp_sizes[consumer.archetype][True]
    for consumer in status_quo_consumers_mean.iter_eligible()
)

# %%
whd_industry_initiatives = 50_000_000

# %% [markdown]
# ### Pure option 1 in report

# %%
new_whd_core = 1_600_000_000

# %%
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
) * 1.05  # adding VAT to discount
unit_discount_gas = (
    core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# %%
# Update revenue
base_pc = rebalanced_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_gas_tariff = gas_tariff.update_policy_costs(base_pc)
base_electricity_tariff = electricity_tariff.update_policy_costs(base_pc)

# %%
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
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
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

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_consumers_unit_discount.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Identifying optimal unit discount value for pure option 1

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 19
unit_discount_gas = 19

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# Update revenue
base_pc = rebalanced_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_gas_tariff = gas_tariff.update_policy_costs(base_pc)
base_electricity_tariff = electricity_tariff.update_policy_costs(base_pc)

# Create ConsumerCollection
base_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_gas_tariff,
    electricity_tariff=base_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_consumers_unit_discount_mean = (
    base_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# Median consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 23
unit_discount_gas = 23

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# Update revenue
base_pc = rebalanced_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_gas_tariff = gas_tariff.update_policy_costs(base_pc)
base_electricity_tariff = electricity_tariff.update_policy_costs(base_pc)

# Create ConsumerCollection
base_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="CORE",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=base_gas_tariff,
    electricity_tariff=base_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_consumers_unit_discount_median = (
    base_consumers_median.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Base median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_consumers_unit_discount_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Identifying optimal discount value for core with GBIS removal

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 17
unit_discount_gas = 17

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
# Create ConsumerCollection
base_delete_gbis_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_delete_gbis_gas_tariff,
    electricity_tariff=base_delete_gbis_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_gbis_consumers_unit_discount_mean = (
    base_delete_gbis_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base + delete gbis mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_gbis_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# Median consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 22
unit_discount_gas = 22

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
# Create ConsumerCollection
base_delete_gbis_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=base_delete_gbis_gas_tariff,
    electricity_tariff=base_delete_gbis_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_gbis_consumers_unit_discount_median = (
    base_delete_gbis_consumers_median.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Base + delete gbis median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_gbis_consumers_unit_discount_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Identifying optimal discount value for core + remove GBIS + remove 1/3 ECO4

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 15
unit_discount_gas = 15

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
# Add rebalancing weights for ECO4 to existing rebalancing dictionary for RO, FiT and GBIS
rebalancing_weights_delete_third_eco = copy.deepcopy(rebalancing_weights_delete_gbis)
rebalancing_weights_delete_third_eco["eco4"] = {
    "new_electricity_weight": 1 / 3,
    "new_gas_weight": 1 / 3,
    "new_tax_weight": 1 / 3,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
base_delete_third_eco_pc = pc.rebalance_levies(
    rebalancing_weights_delete_third_eco,
    scenario_name="rebalance_ro_fit_to_gas_third_eco_to_tax",
)

# Update revenue
base_delete_third_eco_pc = base_delete_third_eco_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_delete_third_eco_gas_tariff = gas_tariff.update_policy_costs(
    base_delete_third_eco_pc
)
base_delete_third_eco_electricity_tariff = electricity_tariff.update_policy_costs(
    base_delete_third_eco_pc
)

# %%
# Create ConsumerCollection
base_delete_third_eco_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS and 1/3 ECO4 on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_delete_third_eco_gas_tariff,
    electricity_tariff=base_delete_third_eco_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_third_eco_consumers_unit_discount_mean = (
    base_delete_third_eco_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base + delete gbis + third eco mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_third_eco_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# Median consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 20
unit_discount_gas = 20
# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
# Add rebalancing weights for ECO4 to existing rebalancing dictionary for RO, FiT and GBIS
rebalancing_weights_delete_third_eco = copy.deepcopy(rebalancing_weights_delete_gbis)
rebalancing_weights_delete_third_eco["eco4"] = {
    "new_electricity_weight": 1 / 3,
    "new_gas_weight": 1 / 3,
    "new_tax_weight": 1 / 3,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# Apply rebalancing weights
base_delete_third_eco_pc = pc.rebalance_levies(
    rebalancing_weights_delete_third_eco,
    scenario_name="rebalance_ro_fit_to_gas_third_eco_to_tax",
)

# Update revenue
base_delete_third_eco_pc = base_delete_third_eco_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_delete_third_eco_gas_tariff = gas_tariff.update_policy_costs(
    base_delete_third_eco_pc
)
base_delete_third_eco_electricity_tariff = electricity_tariff.update_policy_costs(
    base_delete_third_eco_pc
)

# %%
# Create ConsumerCollection
base_delete_third_eco_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS and 1/3 ECO4 on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=base_delete_third_eco_gas_tariff,
    electricity_tariff=base_delete_third_eco_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_third_eco_consumers_unit_discount_median = (
    base_delete_third_eco_consumers_median.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Base + delete gbis + third eco median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_third_eco_consumers_unit_discount_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Identifying optimal discount value for core + remove GBIS + remove ECO4

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 13
unit_discount_gas = 13

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
# Create ConsumerCollection
base_delete_eco_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS and ECO4 on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_delete_eco_gas_tariff,
    electricity_tariff=base_delete_eco_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_eco_consumers_unit_discount_mean = (
    base_delete_eco_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base + delete gbis + eco mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_eco_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# Median consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 17
unit_discount_gas = 17

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
# Create ConsumerCollection
base_delete_eco_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="CORE with GBIS and ECO4 on taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=base_delete_eco_gas_tariff,
    electricity_tariff=base_delete_eco_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_delete_eco_consumers_unit_discount_median = (
    base_delete_eco_consumers_median.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Base + delete gbis + eco median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_delete_eco_consumers_unit_discount_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Pure option 2 in report

# %%
new_whd_core = 1_600_000_000

# %%
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
) * 1.05  # adding VAT to discount
unit_discount_gas = (
    core_target_spending_gas / cwp_recipients_gas_consumption * 1.05
)  # adding VAT to discount

# %%
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

# %%
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
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
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

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base half whd"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_consumers_unit_discount.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %% [markdown]
# ### Identifying optimal unit discount value for pure option 2

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 16
unit_discount_gas = 16

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
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
base_half_whd_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_consumers_unit_discount_mean = (
    base_half_whd_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base half whd mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %%
# What is the publicly funded part of WHD revenue?
(base_half_whd_pc["whd"].tax_weight * base_half_whd_pc["whd"].revenue) / 1e9

# %% [markdown]
# Median consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 20
unit_discount_gas = 20

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
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

# %%
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
base_half_whd_consumers_median = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh_50PCT",
    electricity_consumption_col="ElectricitySingleRatekWh_50PCT",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_consumers_unit_discount_median = (
    base_half_whd_consumers_median.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo median"
adjusted_scenario = "Base half whd median"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_median.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_consumers_unit_discount_median.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %%
# What is the publicly funded part of WHD revenue?
(base_half_whd_pc["whd"].tax_weight * base_half_whd_pc["whd"].revenue) / 1e9

# %% [markdown]
# ### Identifying optimal discount value for option 2 with GBIS removal

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 15
unit_discount_gas = 15

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
# Add rebalancing weights to existing rebalancing dictionary
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
base_half_whd_delete_gbis_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_gbis,
    scenario_name="rebalance_ro_fit_to_gas_whd_half_to_tax_delete_gbis",
)

# %%
# Update revenue
base_half_whd_delete_gbis_pc = base_half_whd_delete_gbis_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_half_whd_gas_tariff = gas_tariff.update_policy_costs(base_half_whd_delete_gbis_pc)
base_half_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_half_whd_delete_gbis_pc
)

# Create ConsumerCollection
base_half_whd_delete_gbis_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_delete_gbis_consumers_unit_discount_mean = (
    base_half_whd_delete_gbis_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base half whd delete gbis mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_delete_gbis_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %%
# What is publicly funded?
(
    (
        base_half_whd_delete_gbis_pc["whd"].tax_weight
        * base_half_whd_delete_gbis_pc["whd"].revenue
    )
    + (
        base_half_whd_delete_gbis_pc["gbis"].tax_weight
        * base_half_whd_delete_gbis_pc["gbis"].revenue
    )
) / 1e9

# %% [markdown]
# ### Identifying optimal discount value for option 2 with GBIS + 1/3 ECO4 removal

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 14
unit_discount_gas = 14

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
# Add rebalancing weights to existing rebalancing dictionary
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
base_half_whd_delete_gbis_third_eco_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_gbis_third_eco,
    scenario_name="rebalance_ro_fit_to_gas_half_whd_delete_gbis_third_eco",
)

# Update revenue
base_half_whd_delete_gbis_third_eco_pc = (
    base_half_whd_delete_gbis_third_eco_pc.update_revenues(
        {"whd": (new_whd_core + whd_industry_initiatives)}
    )
)

# Update tariffs
base_half_whd_gas_tariff = gas_tariff.update_policy_costs(
    base_half_whd_delete_gbis_third_eco_pc
)
base_half_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_half_whd_delete_gbis_third_eco_pc
)

# %%
# Create ConsumerCollection
base_half_whd_delete_gbis_third_eco_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_delete_gbis_third_eco_consumers_unit_discount_mean = base_half_whd_delete_gbis_third_eco_consumers_mean.apply_support_to_eligible_consumers(
    "electricity",
    unit_discount_electricity,
    "unit discount",
    inplace=False,
).apply_support_to_eligible_consumers(
    "gas", unit_discount_gas, "unit discount", inplace=False
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base half whd delete gbis third eco mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_delete_gbis_third_eco_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %%
# What is publicly funded?
(
    (
        base_half_whd_delete_gbis_third_eco_pc["whd"].tax_weight
        * base_half_whd_delete_gbis_third_eco_pc["whd"].revenue
    )
    + (
        base_half_whd_delete_gbis_third_eco_pc["gbis"].tax_weight
        * base_half_whd_delete_gbis_third_eco_pc["gbis"].revenue
    )
    + (
        base_half_whd_delete_gbis_third_eco_pc["eco4"].tax_weight
        * base_half_whd_delete_gbis_third_eco_pc["eco4"].revenue
    )
) / 1e9

# %% [markdown]
# ### Identifying optimal discount value for option 2 (half whd) + remove GBIS + remove ECO4

# %% [markdown]
# Mean consumers

# %%
# Define unit discounts for electricity and gas - EXPERIMENT
unit_discount_electricity = 11
unit_discount_gas = 11

# Allocate spending to electricity and gas discount
core_target_spending_electricity = (
    unit_discount_electricity / 1.05
) * cwp_recipients_electricity_consumption
core_target_spending_gas = (unit_discount_gas / 1.05) * cwp_recipients_gas_consumption

# Calculate needed spending
new_whd_core = core_target_spending_electricity + core_target_spending_gas

# %%
# Add rebalancing weights to existing rebalancing dictionary
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
base_half_whd_delete_eco_pc = pc.rebalance_levies(
    rebalancing_weights_half_whd_delete_eco,
    scenario_name="rebalance_ro_fit_to_gas_half_whd_delete_eco",
)

# Update revenue
base_half_whd_delete_eco_pc = base_half_whd_delete_eco_pc.update_revenues(
    {"whd": (new_whd_core + whd_industry_initiatives)}
)

# Update tariffs
base_half_whd_gas_tariff = gas_tariff.update_policy_costs(base_half_whd_delete_eco_pc)
base_half_whd_electricity_tariff = electricity_tariff.update_policy_costs(
    base_half_whd_delete_eco_pc
)

# %%
# Create ConsumerCollection
base_half_whd_delete_eco_consumers_mean = ConsumerCollection.from_dataframe(
    collection_name="CORE with 1/2 of WHD revenue from general taxation",
    df=ofgem_archetypes_df,
    rows=range(1, 25),
    name_col="AnnualConsumptionProfile",
    archetype_col="AnnualConsumptionProfile",
    net_annual_income_col="NetAnnualHouseholdIncome",
    net_income_decile_col="NetIncomeDecile",
    main_heating_fuel_col="ArchetypeHeatingFuel",
    gas_consumption_col="GaskWh",
    electricity_consumption_col="ElectricitySingleRatekWh",
    gas_tariff=base_half_whd_gas_tariff,
    electricity_tariff=base_half_whd_electricity_tariff,
    unmetered_fuel_spend_col="UnmeteredFuelSpend",
    unit_converter=1_000,
    model_eligibility_sets=True,
)

# Unit discount approach: Gas and electricity
# Apply support to eligible consumers
base_half_whd_delete_eco_consumers_unit_discount_mean = (
    base_half_whd_delete_eco_consumers_mean.apply_support_to_eligible_consumers(
        "electricity",
        unit_discount_electricity,
        "unit discount",
        inplace=False,
    ).apply_support_to_eligible_consumers(
        "gas", unit_discount_gas, "unit discount", inplace=False
    )
)

# %%
baseline_scenario = "Status quo mean"
adjusted_scenario = "Base half whd delete eco mean"
consumers_df = pd.concat(
    [
        status_quo_consumers_flat_rebate_mean.tidy_summary_consumers(
            scenario_name=baseline_scenario
        ),
        base_half_whd_delete_eco_consumers_unit_discount_mean.tidy_summary_consumers(
            scenario_name=adjusted_scenario
        ),
    ]
)

# %%
master_summary_flourish = consumers_df.pivot_table(
    index=[
        "Name",
        "Scenario",
        "Eligible for support",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()
master_summary_flourish = master_summary_flourish[
    [
        "Name",
        "Eligible for support",
        "Scenario",
        "main_heating_fuel",
        "combined_fuel_bill",
    ]
].sort_values(by=["Name"])

master_summary_flourish = master_summary_flourish.rename(
    columns={
        "Eligible for support": "EligibleForSupport",
    }
)

master_summary_flourish = master_summary_flourish.copy(deep=True)
bill_changes = []
for row in master_summary_flourish.itertuples(index=False):
    # Get baseline bill
    baseline_bill = master_summary_flourish.loc[
        (master_summary_flourish["Name"] == row.Name)
        & (master_summary_flourish["Scenario"] == baseline_scenario)
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

df = master_summary_flourish[master_summary_flourish["Scenario"] == adjusted_scenario]
df["Eligibility"] = "CWP"
# Add group sizes
eligibility_size_lookup = {
    "CWP": cwp_sizes,
}
group_sizes = []
for row in df.itertuples(index=False):
    size = (
        eligibility_size_lookup.get(row.Eligibility)
        .get(row.Name)
        .get(row.EligibleForSupport)
    )
    group_sizes.append(size)
df.loc[:, "GroupSize"] = group_sizes

# %%
# Are there any eligible households with a bill rise?
(df[df["EligibleForSupport"] == True]["Net change in annual energy bill"] > 0).any()

# %%
# What is the range of bill change for gas-using households ineligible for support?
df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].min(), df[(df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")][
    "Net change in annual energy bill"
].max()

# %%
# What is the weighted average bill change for gas-using households ineligible for support
filtered_df = df[
    (df["EligibleForSupport"] == False) & (df["main_heating_fuel"] == "Gas")
]
(
    filtered_df["Net change in annual energy bill"] * filtered_df["GroupSize"]
).sum() / filtered_df["GroupSize"].sum()

# %%
# What is the WHD revenue?
print(str((new_whd_core + whd_industry_initiatives) / 1e9), "billion")

# %%
# What is publicly funded?
(
    (
        base_half_whd_delete_eco_pc["whd"].tax_weight
        * base_half_whd_delete_eco_pc["whd"].revenue
    )
    + (
        base_half_whd_delete_eco_pc["gbis"].tax_weight
        * base_half_whd_delete_eco_pc["gbis"].revenue
    )
    + (
        base_half_whd_delete_eco_pc["eco4"].tax_weight
        * base_half_whd_delete_eco_pc["eco4"].revenue
    )
) / 1e9

# %%


# %%
