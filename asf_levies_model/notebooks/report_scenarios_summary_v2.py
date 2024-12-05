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
import copy
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
    ofgem_archetypes_scheme_eligibility,
    ofgem_archetypes_net_income_deciles_full,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.summary import (
    _rebalance_levies,
    create_scenario_weights_dict,
    calculate_cost_stream,
    set_common_denominators,
    calculate_fuel_poverty_rates,
)

from asf_levies_model import config, PROJECT_DIR

from asf_levies_model.consumers import Consumer

# %% [markdown]
# **Status quo levies from Annex 4**

# %%
# Assign denominator values
supply_elec = 94_200_366
supply_gas = 265_197_947
customers_gas = 24_503_683
customers_elec = 29_078_770

# %%
# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %%
# Instantiate status quo levies with Annex 4 data
fileobject = download_annex_4(as_fileobject=True)
levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=supply_elec),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=supply_elec),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=customers_gas),
    WHD.from_dataframe(process_data_WHD(fileobject)),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(
        process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
]
fileobject.close()

# %%
# Create dictionary of denominators for each levy
denominators = set_common_denominators(
    levies, supply_elec, supply_gas, customers_gas, customers_elec
)

# %% [markdown]
# **Defining rebalancing weights for each scenario**

# %%
# Scenario 1: Status quo weights which reflect denominators
status_quo = create_scenario_weights_dict(levies)

# Manually update WHD weights according to denominator balance
status_quo["whd"]["new_electricity_weight"] = denominators["whd"]["customers_elec"] / (
    denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]
)
status_quo["whd"]["new_gas_weight"] = denominators["whd"]["customers_gas"] / (
    denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]
)

# Rebalance baseline levies to reflect denominators
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# %%
# Scenario 2: Weights for full removal of policy costs on electricity
sq_electricity_removal_weights = create_scenario_weights_dict(levies)

# Remove all levies on electricity to general taxation
for levy in [levy.short_name for levy in levies if levy.electricity_weight > 0]:
    sq_electricity_removal_weights[levy]["new_tax_weight"] = (
        sq_electricity_removal_weights[levy]["new_electricity_weight"]
    )

    for weight_type in [
        "new_electricity_weight",
        "new_variable_weight_elec",
        "new_fixed_weight_elec",
    ]:
        sq_electricity_removal_weights[levy][weight_type] = 0

# %%
# Scenario 3:  Weights for removal to general taxation of RO and FIT only
remove_ro_fit_weights = create_scenario_weights_dict(levies)

# Remove RO and FIT levies on electricity to general taxation
for levy in ["ro", "fit"]:

    remove_ro_fit_weights[levy]["new_tax_weight"] = remove_ro_fit_weights[levy][
        "new_electricity_weight"
    ]

    for weight_type in [
        "new_electricity_weight",
        "new_variable_weight_elec",
        "new_fixed_weight_elec",
    ]:
        remove_ro_fit_weights[levy][weight_type] = 0

# %%
# Scenario 4:  Weights for full rebalancing from electricity to all gas
sq_all_gas_weights = create_scenario_weights_dict(levies)

for levy in [levy for levy in levies if levy.electricity_weight > 0]:
    sq_all_gas_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# Scenario 5:  Weights for rebalancing from electricity to gas of RO and FIT only
rebalance_ro_fit_weights = create_scenario_weights_dict(levies)

for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
    rebalance_ro_fit_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# Scenario 6: Weights for Double WHD, full removal on electricity
# Weights are the same as Scenario 2
double_whd_electricity_removal_weights = sq_electricity_removal_weights

# %%
# Scenario 7: Weights for Double WHD, full rebalancing to gas
# Weights are the same as Scenario 4
double_whd_all_gas_weights = sq_all_gas_weights

# %%
# Create a dictionary of {scenario name: rebalancing weights}
scenario_weights = {
    "2. Remove all electricity": sq_electricity_removal_weights,
    "3. Remove RO and FIT": remove_ro_fit_weights,
    "4. Rebalance all electricity to gas": sq_all_gas_weights,
    "5. Rebalance RO and FIT to gas": rebalance_ro_fit_weights,
    "6. Double WHD and remove all electricity": double_whd_electricity_removal_weights,
    "7. Double WHD and rebalance all electricity to gas": double_whd_all_gas_weights,
}

# %%
# Distinguish between scenarios using status quo levies set and scenarios using double WHD levies set
scenarios_set_1 = list(scenario_weights.keys())[:4]
scenarios_set_2 = list(scenario_weights.keys())[-2:]

# %% [markdown]
# **Levies for each scenario**

# %%
# Create a dictionary of {scenario name: levies}

# Populate dictionary with scenarios using status quo levies
scenario_levies = {"baseline": levies}

for scenario_name in scenarios_set_1:
    scenario_levies[scenario_name] = _rebalance_levies(
        levies, scenario_weights, denominators, scenario_name
    )


# Create set of levy objects with double WHD revenue
double_whd_levies = copy.deepcopy(levies)
# The update revenue method automatically updates the levy rates for the levy given the revised revenue amount
double_whd_levies[3] = double_whd_levies[3].update_revenue(
    new_revenue=double_whd_levies[3].revenue * 2,
    **denominators[double_whd_levies[3].short_name],
)

# Populate dictionary with scenarios using levies with double WHD
for scenario_name in scenarios_set_2:
    scenario_levies[scenario_name] = _rebalance_levies(
        double_whd_levies, scenario_weights, denominators, scenario_name
    )

# %% [markdown]
# **Tariffs for each scenario**

# %%
# Load tariff (Other Payment method) data from Annex 9
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
# Create a dictionary of {scenario name: tariffs}

# Populate dictionary of electricity tariffs
baseline_elec_tariff = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)
baseline_elec_tariff.name = "baseline " + baseline_elec_tariff.name
elec_tariffs = {"baseline": baseline_elec_tariff}

for scenario_name in scenario_weights.keys():
    baseline_tariff = ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    )
    baseline_tariff.name = str(scenario_name) + ": " + baseline_tariff.name
    elec_tariffs[scenario_name] = baseline_tariff

# Populate dictionary for gas tariffs
baseline_gas_tariff = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)
baseline_gas_tariff.name = "baseline " + baseline_gas_tariff.name
gas_tariffs = {"baseline": baseline_gas_tariff}

for scenario_name in scenario_weights.keys():
    baseline_tariff = GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    )
    baseline_tariff.name = str(scenario_name) + ": " + baseline_tariff.name
    gas_tariffs[scenario_name] = baseline_tariff

# %%
# Update baseline tariff policy costs to match denominator adjusted policy costs
elec_tariffs["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, True, False) for levy in levies]
)
elec_tariffs["baseline"].pc = sum(
    [levy.calculate_levy(1, 0, False, False) for levy in levies]
)
gas_tariffs["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, False, True) for levy in levies]
)
gas_tariffs["baseline"].pc = sum(
    [levy.calculate_levy(0, 1, False, False) for levy in levies]
)

# %%
# Update tariff policy costs with rebalanced levies
for scenario_name in scenario_weights.keys():
    elec_tariffs[scenario_name].pc_nil = sum(
        [
            levy.calculate_levy(0, 0, True, False)
            for levy in scenario_levies[scenario_name]
        ]
    )
    elec_tariffs[scenario_name].pc = sum(
        [
            levy.calculate_levy(1, 0, False, False)
            for levy in scenario_levies[scenario_name]
        ]
    )
    gas_tariffs[scenario_name].pc_nil = sum(
        [
            levy.calculate_levy(0, 0, False, True)
            for levy in scenario_levies[scenario_name]
        ]
    )
    gas_tariffs[scenario_name].pc = sum(
        [
            levy.calculate_levy(0, 1, False, False)
            for levy in scenario_levies[scenario_name]
        ]
    )

# %% [markdown]
# **Consumers for each scenario**

# %%
# Load archetypes headline data
ofgem_archetypes_df = ofgem_archetypes_data()

# %%
# Create a dictionary of {scenario name: list of Consumers} (Typical and average Ofgem archetypes only, n=25)
scenarios_set_1.insert(0, "baseline")

consumers = {}
# Scenarios set without WHD eligibility criteria
for scenario_name in scenarios_set_1:
    consumers[scenario_name] = [
        Consumer.consumer_from_dataframe(
            df=ofgem_archetypes_df,
            row=row,
            name_col="AnnualConsumptionProfile",
            archetype_col="AnnualConsumptionProfile",
            net_annual_income_col="NetAnnualHouseholdIncome",
            main_heating_fuel_col="ArchetypeHeatingFuel",
            gas_consumption_col="GaskWh",
            electricity_consumption_col="ElectricitySingleRatekWh",
            gas_tariff=gas_tariffs[scenario_name],
            electricity_tariff=elec_tariffs[scenario_name],
            unit_converter=1_000,
        )
        for row in range(25)
    ]

# %% [markdown]
# We need to instantiate two sets of Consumer objects for the double WHD scenarios - one set that is eligible and one set that is ineligible.

# %%
# Creating an input dataframe that has two sets of profiles - eligible and ineligible
ofgem_archetypes_df_eligible = ofgem_archetypes_df.copy(deep=True)
ofgem_archetypes_df_eligible = ofgem_archetypes_df_eligible.iloc[0:25]
ofgem_archetypes_df_eligible["whd_eligible"] = True

ofgem_archetypes_df_ineligible = ofgem_archetypes_df_eligible.copy(deep=True)
ofgem_archetypes_df_ineligible["whd_eligible"] = False

ofgem_archetypes_df_whd_eligibility = pd.concat(
    [ofgem_archetypes_df_eligible, ofgem_archetypes_df_ineligible], ignore_index=True
)

# %%
# Scenarios with WHD eligibility criteria

# Eligible and ineligible Consumers set for baseline scenario
consumers["baseline with whd eligibility"] = [
    Consumer.consumer_from_dataframe(
        df=ofgem_archetypes_df_whd_eligibility,
        row=row,
        name_col="AnnualConsumptionProfile",
        net_annual_income_col="NetAnnualHouseholdIncome",
        archetype_col="AnnualConsumptionProfile",
        main_heating_fuel_col="ArchetypeHeatingFuel",
        gas_consumption_col="GaskWh",
        electricity_consumption_col="ElectricitySingleRatekWh",
        gas_tariff=gas_tariffs["baseline"],
        electricity_tariff=elec_tariffs["baseline"],
        unit_converter=1_000,
        scheme_eligible_col="whd_eligible",
    )
    for row in range(len(ofgem_archetypes_df_whd_eligibility))
]

# Eligible and ineligible Consumers set for each double WHD scenario
for scenario_name in scenarios_set_2:
    consumers[scenario_name] = [
        Consumer.consumer_from_dataframe(
            df=ofgem_archetypes_df_whd_eligibility,
            row=row,
            name_col="AnnualConsumptionProfile",
            archetype_col="AnnualConsumptionProfile",
            net_annual_income_col="NetAnnualHouseholdIncome",
            main_heating_fuel_col="ArchetypeHeatingFuel",
            gas_consumption_col="GaskWh",
            electricity_consumption_col="ElectricitySingleRatekWh",
            gas_tariff=gas_tariffs[scenario_name],
            electricity_tariff=elec_tariffs[scenario_name],
            unit_converter=1_000,
            scheme_eligible_col="whd_eligible",
        )
        for row in range(len(ofgem_archetypes_df_whd_eligibility))
    ]

# Create unique names by modifying name attributes of consumers to reflect eligibility
scenarios_set_2.insert(0, "baseline with whd eligibility")
for scenario in scenarios_set_2:
    for consumer in consumers[scenario]:
        if consumer.scheme_eligible == True:
            consumer.name = consumer.name + " Eligible"
        elif consumer.scheme_eligible == False:
            consumer.name = consumer.name + " Ineligible"
        else:
            raise ValueError("No eligibility specified")

# %%
# Apply £150 discount to eligible consumers for baseline scenario considering eligibility
for consumer in consumers["baseline with whd eligibility"]:
    if consumer.scheme_eligible == True:
        consumer.apply_social_support_adjustment(
            adjustment_fuel="electricity",
            adjustment_parameter=-150,
            adjustment_mode="flat adjustment",
        )

# Apply £300 discount to eligible consumers in double WHD scenarios
for scenario in scenarios_set_2[1:3]:
    for consumer in consumers[scenario]:
        if consumer.scheme_eligible == True:
            consumer.apply_social_support_adjustment(
                adjustment_fuel="electricity",
                adjustment_parameter=-300,
                adjustment_mode="flat adjustment",
            )

# %% [markdown]
# **Results dataframe for scenarios 1 (Baseline) to 5**

# %%
# Create a summary dataframe, in tidy format, for all consumer profiles and scenarios
tidy_summary_1 = pd.DataFrame()
for scenario in scenarios_set_1:
    tidy = pd.concat([consumer.get_tidy_summary() for consumer in consumers[scenario]])

    tidy["scenario"] = scenario

    tidy_summary_1 = pd.concat([tidy_summary_1, tidy])

# %%
# Reshaping to recreate Martina's table for the summary chart
tidy_summary_1["scenario"] = tidy_summary_1["scenario"].replace(
    "baseline", "1. Baseline"
)

scenarios_summary_chart_1 = tidy_summary_1.pivot_table(
    index=[
        "Name",
        "scenario",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()

# %%
scenarios_summary_chart_1 = scenarios_summary_chart_1[
    [
        "Name",
        "scenario",
        "main_heating_fuel",
        "electricity_bill",
        "gas_bill",
        "dual_fuel_bill",
    ]
].sort_values(by=["scenario", "Name"])

# Create new column for bill change from baseline
baseline = scenarios_summary_chart_1[
    scenarios_summary_chart_1["scenario"] == "1. Baseline"
].set_index("Name")["dual_fuel_bill"]

scenarios_summary_chart_1["Bill change from baseline"] = (
    scenarios_summary_chart_1.apply(
        lambda row: row["dual_fuel_bill"] - baseline.get(row["Name"], 0),
        axis=1,
    )
)

scenarios_summary_chart_1 = scenarios_summary_chart_1.reset_index(drop=True)

# %% [markdown]
# **Results dataframe for scenarios 1 alternative (Double WHD Baseline), 6 and 7**

# %%
# Create a summary dataframe, in tidy format, for all consumer profiles and scenarios
tidy_summary_2 = pd.DataFrame()
for scenario in scenarios_set_2:
    tidy = pd.concat([consumer.get_tidy_summary() for consumer in consumers[scenario]])

    tidy["scenario"] = scenario

    tidy_summary_2 = pd.concat([tidy_summary_2, tidy])

# %%
# Reshaping to recreate Martina's table for the summary chart
tidy_summary_2["scenario"] = tidy_summary_2["scenario"].replace(
    "baseline with whd eligibility", "1. Baseline"
)

scenarios_summary_chart_2 = tidy_summary_2.pivot_table(
    index=[
        "Name",
        "scenario",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()

scenarios_summary_chart_2 = scenarios_summary_chart_2[
    [
        "Name",
        "archetype",
        "scheme_eligible",
        "scenario",
        "main_heating_fuel",
        "electricity_bill",
        "gas_bill",
        "dual_fuel_bill",
    ]
].sort_values(by=["scenario", "Name"])

# Create new column for bill change from baseline
baseline = scenarios_summary_chart_2[
    scenarios_summary_chart_2["scenario"] == "1. Baseline"
].set_index("Name")["dual_fuel_bill"]

scenarios_summary_chart_2["Bill change from baseline"] = (
    scenarios_summary_chart_2.apply(
        lambda row: row["dual_fuel_bill"] - baseline.get(row["Name"], 0),
        axis=1,
    )
)

scenarios_summary_chart_2 = scenarios_summary_chart_2.reset_index(drop=True)

# %%
# Construct look up table for full archetype and WHD eligible/ineligible size
archetype_size = ofgem_archetypes_df[:25]
archetype_size = archetype_size[["AnnualConsumptionProfile", "ArchetypeSize"]]

eligibility_size = ofgem_archetypes_scheme_eligibility()
whd_eligibility_size = (
    eligibility_size[["AnnualConsumptionProfile", "WHDEligibleSize"]]
    .set_index("AnnualConsumptionProfile")
    .astype("Int64")
)

whd_eligibility_df = archetype_size.merge(
    whd_eligibility_size,
    how="left",
    left_on="AnnualConsumptionProfile",
    right_index=True,
)

whd_eligibility_df.loc[0, "ArchetypeSize"] = 0
whd_eligibility_df.loc[0, "WHDEligibleSize"] = 0

whd_eligibility_df["WHDIneligibleSize"] = (
    whd_eligibility_df["ArchetypeSize"] - whd_eligibility_df["WHDEligibleSize"]
)

# %%
# Add column with original archetype name
scenarios_summary_chart_2["AnnualConsumptionProfile"] = scenarios_summary_chart_2[
    "Name"
].str.extract(r"(\w+)")

# Merge summary dataframe with look up dataframe on original archetype name
scenarios_summary_chart_2 = scenarios_summary_chart_2.merge(
    whd_eligibility_df, on="AnnualConsumptionProfile", how="left"
)

# Add column for size based on scheme_eligible
scenarios_summary_chart_2["size"] = scenarios_summary_chart_2.apply(
    lambda row: (
        row["WHDEligibleSize"] if row["scheme_eligible"] else row["WHDIneligibleSize"]
    ),
    axis=1,
)

# Drop processing columns
scenarios_summary_chart_2 = scenarios_summary_chart_2.drop(
    columns=[
        "ArchetypeSize",
        "WHDEligibleSize",
        "WHDIneligibleSize",
        "AnnualConsumptionProfile",
    ]
)

# %% [markdown]
# **Electricity to gas unit cost ratios**

# %%
# Calculate electricity-to-gas cost ratios for both sets of scenarios
scenarios = ["baseline"] + list(scenario_weights.keys())

scenario_ratios = [
    elec_tariffs[scenario].calculate_variable_consumption(1)
    / gas_tariffs[scenario].calculate_variable_consumption(1)
    for scenario in scenarios
]

cost_ratio_frame = pd.DataFrame(
    {"Scenario": scenarios, "Electricity to gas unit cost ratio": scenario_ratios}
).reset_index(drop=True)

# %% [markdown]
# **Total cost to gas, electricity and general taxation for each scenario**

# %%
revenue_streams_df = pd.DataFrame()

# Calculate cos streams for baseline
scenario_weights["baseline"] = status_quo
baseline_row = calculate_cost_stream("baseline", scenario_weights, levies)
revenue_streams_df = pd.concat([revenue_streams_df, baseline_row])

# Calculate cost streams for all rebalancing scenarios
for scenario in list(scenario_weights.keys())[:4]:
    scenario_row = calculate_cost_stream(scenario, scenario_weights, levies)
    revenue_streams_df = pd.concat([revenue_streams_df, scenario_row])

for scenario in list(scenario_weights.keys())[4:6]:
    scenario_row = calculate_cost_stream(scenario, scenario_weights, double_whd_levies)
    revenue_streams_df = pd.concat([revenue_streams_df, scenario_row])

revenue_streams_df = revenue_streams_df.reset_index(drop=True)

# Rename and reorder columns
revenue_streams_df["Scenario"] = revenue_streams_df["Scenario"].replace(
    "baseline", "1. Baseline"
)
first_col = revenue_streams_df.pop("Scenario")
revenue_streams_df.insert(0, "Scenario", first_col)
revenue_streams_df = revenue_streams_df.sort_values(by="Scenario")

# %% [markdown]
# **Fuel poverty rates**

# %%
# Load archetype income deciles data
archetypes_net_income_deciles_full_df = ofgem_archetypes_net_income_deciles_full()

# Drop rows with no households in income decile
archetypes_net_income_deciles_full_df = archetypes_net_income_deciles_full_df[
    archetypes_net_income_deciles_full_df["size"] != 0
]

archetypes_net_income_deciles_full_df = (
    archetypes_net_income_deciles_full_df.reset_index(drop=True)
)

# %%
# Create a dictionary of {scenario name: list of Consumers by archetype income decile} (Typical and average Ofgem archetypes only, n=25)

consumers = {}

for scenario_name in list(scenario_weights.keys()):
    consumers[scenario_name] = [
        Consumer.consumer_from_dataframe(
            df=archetypes_net_income_deciles_full_df,
            row=row,
            name_col="name",
            archetype_col="name",
            net_annual_income_col="net_annual_income",
            net_income_decile_col="net_income_decile",
            main_heating_fuel_col="main_heating_fuel",
            gas_consumption_col="gas_consumption",
            electricity_consumption_col="electricity_consumption",
            unmetered_fuel_spend_col="unmetered_fuel_spend",
            size_col="size",
            gas_tariff=gas_tariffs[scenario_name],
            electricity_tariff=elec_tariffs[scenario_name],
            unit_converter=1_000,
        )
        for row in range(len(archetypes_net_income_deciles_full_df))
    ]

# Create unique names by modifying name attribute to reflect income decile
for scenario_name in list(scenario_weights.keys()):
    for consumer in consumers[scenario_name]:
        consumer.name = consumer.archetype + "_" + str(consumer.net_income_decile)

# %%
# Estimate fuel poverty rates for each archetype
percentage_in_fuel_poverty_df = calculate_fuel_poverty_rates(
    consumers, list(scenario_weights.keys())
)

# Reorder columns
columns = list(percentage_in_fuel_poverty_df.columns)
last_column = columns.pop(-1)
columns.insert(1, last_column)
percentage_in_fuel_poverty_df = percentage_in_fuel_poverty_df[columns]

# %% [markdown]
# **Saving all output dataframes to Excel workbook**

# %%
# Get today's date
today = datetime.now()

# Format today's date (e.g., YYYY-MM-DD)
date_str = today.strftime("%Y%m%d")

# Define the filename with today's date
filename = f"{PROJECT_DIR}/outputs/data/scenarios_data_{date_str}.xlsx"

# %%
# Create an Excel writer object
with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
    # Write each DataFrame to a different sheet
    scenarios_summary_chart_1.to_excel(
        writer, sheet_name="Scenarios 1 to 5 summary", index=False
    )
    scenarios_summary_chart_2.to_excel(
        writer, sheet_name="Scenarios 6 and 7 summary", index=False
    )
    cost_ratio_frame.to_excel(writer, sheet_name="Scenario cost ratios", index=False)
    revenue_streams_df.to_excel(
        writer, sheet_name="Scenario revenue streams", index=False
    )
    percentage_in_fuel_poverty_df.to_excel(
        writer, sheet_name="Scenarios fuel poverty rates", index=False
    )
    revenue_streams_df.to_excel(
        writer, sheet_name="Scenario revenue streams", index=False
    )
    ofgem_archetypes_df.to_excel(
        writer, sheet_name="Underlying headline data", index=False
    )

# %%
