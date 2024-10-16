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
    ofgem_archetypes_scheme_eligibility,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.summary import (
    process_rebalancing_scenarios,
    process_rebalancing_scenario_bills,
)

from asf_levies_model import config, PROJECT_DIR

# %%
# Annex 4 and initialise levies
fileobject = download_annex_4(as_fileobject=True)
levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=24_503_683),
    WHD.from_dataframe(process_data_WHD(fileobject)),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(process_data_FIT(fileobject), revenue=689_233_317),
]
fileobject.close()

# %%
# Annex 9 and initialise tariffs (Other Payment method)
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
# Load archetypes headline data
ofgem_archetypes_df = ofgem_archetypes_data()

# %%
# Set denominator values
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

# %%
# Scenario 1: Status quo - Rebalance baseline to reflect denominators
status_quo = {}  # Recreating status quo
for levy in levies:
    status_quo[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

# manually update WHD weights according to denominator balance
status_quo["whd"]["new_electricity_weight"] = round(
    (
        denominators["whd"]["customers_elec"]
        / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"])
    ),
    2,
)
status_quo["whd"]["new_gas_weight"] = round(
    (
        denominators["whd"]["customers_gas"]
        / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"])
    ),
    2,
)

# rebalance baseline levies
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# %%
# Scenario 2: Full removal of policy costs on electricity
sq_electricity_removal_weights = {}

for levy in levies:
    sq_electricity_removal_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

for removed_levy in ["ro", "aahedc", "whd", "eco", "fit"]:

    sq_electricity_removal_weights[removed_levy]["new_tax_weight"] = (
        sq_electricity_removal_weights[removed_levy]["new_electricity_weight"]
    )
    sq_electricity_removal_weights[removed_levy]["new_electricity_weight"] = 0
    sq_electricity_removal_weights[removed_levy]["new_variable_weight_elec"] = 0
    sq_electricity_removal_weights[removed_levy]["new_fixed_weight_elec"] = 0

# %%
# Scenario 3: Status quo with removal of RO and FIT only
remove_ro_fit_weights = {}

for levy in levies:
    remove_ro_fit_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

for removed_levy in ["ro", "fit"]:
    remove_ro_fit_weights[removed_levy]["new_tax_weight"] = 1
    remove_ro_fit_weights[removed_levy]["new_electricity_weight"] = 0
    remove_ro_fit_weights[removed_levy]["new_variable_weight_elec"] = 0
    remove_ro_fit_weights[removed_levy]["new_fixed_weight_elec"] = 0

# %%
# Scenario 4: Full rebalancing from electricity to all gas
sq_all_gas_weights = {}

for levy in levies:
    sq_all_gas_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": (
            levy.gas_variable_weight
            if levy.gas_variable_weight != 0
            else levy.electricity_variable_weight
        ),
        "new_fixed_weight_gas": (
            levy.gas_fixed_weight
            if levy.gas_fixed_weight != 0
            else levy.electricity_fixed_weight
        ),
    }

# %%
# Scenario 5: Status quo with rebalancing of RO and FIT only
rebalance_ro_fit_weights = {}

for levy in levies:
    rebalance_ro_fit_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

for rebalanced_levy in ["ro", "fit"]:
    rebalance_ro_fit_weights[rebalanced_levy]["new_gas_weight"] = (
        rebalance_ro_fit_weights[rebalanced_levy]["new_electricity_weight"]
    )
    rebalance_ro_fit_weights[rebalanced_levy]["new_variable_weight_gas"] = (
        rebalance_ro_fit_weights[rebalanced_levy]["new_variable_weight_elec"]
    )
    rebalance_ro_fit_weights[rebalanced_levy]["new_fixed_weight_gas"] = (
        rebalance_ro_fit_weights[rebalanced_levy]["new_fixed_weight_elec"]
    )
    rebalance_ro_fit_weights[rebalanced_levy]["new_electricity_weight"] = 0
    rebalance_ro_fit_weights[rebalanced_levy]["new_variable_weight_elec"] = 0
    rebalance_ro_fit_weights[rebalanced_levy]["new_fixed_weight_elec"] = 0

# %%
# Define all rebalancing weights for all scenarios
scenario_weights = {
    "2. Remove all electricity": sq_electricity_removal_weights,
    "3. Remove RO and FIT": remove_ro_fit_weights,
    "4. Rebalance all electricity to gas": sq_all_gas_weights,
    "5. Rebalance RO and FIT to gas": rebalance_ro_fit_weights,
}

weights = {}
for scenario_name in scenario_weights.keys():
    weights[scenario_name] = scenario_weights.get(scenario_name)

# %%
# Electricity bills
elec_bills = {
    "baseline": ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
}

for scenario_name in scenario_weights.keys():
    elec_bills[scenario_name] = ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    )

# Gas bills
gas_bills = {
    "baseline": GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
}
for scenario_name in scenario_weights.keys():
    gas_bills[scenario_name] = GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    )

# Update baseline bill policy costs to match denominator adjusted policy costs
elec_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, True, False) for levy in levies]
)
elec_bills["baseline"].pc = sum(
    [levy.calculate_levy(1, 0, False, False) for levy in levies]
)
gas_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, False, True) for levy in levies]
)
gas_bills["baseline"].pc = sum(
    [levy.calculate_levy(0, 1, False, False) for levy in levies]
)

# %%
# Generate scenario outputs
scenario_outputs = process_rebalancing_scenarios(
    levies,
    weights,
    denominators,
    ofgem_archetypes_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    ["fixed", "variable", "total"],
    1_000,
)

scenario_bill_outputs = process_rebalancing_scenario_bills(
    elec_bills,
    gas_bills,
    levies,
    weights,
    denominators,
    ofgem_archetypes_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    1_000,
    True,
)

scenario_outputs = pd.concat([scenario_outputs, scenario_bill_outputs])

# %%
# Reshaping to recreate Martina's table for the summary chart
scenario_outputs["scenario"] = scenario_outputs["scenario"].replace(
    "Baseline", "1. Baseline"
)

scenarios_summary_chart = scenario_outputs.pivot_table(
    index=[
        "AnnualConsumptionProfile",
        "scenario",
    ],
    columns="variable",
    values="value",
    aggfunc="sum",
).reset_index()

scenarios_summary_chart = scenarios_summary_chart[
    [
        "AnnualConsumptionProfile",
        "scenario",
        "ArchetypeHeatingFuel",
        "ArchetypeSize",
        "total bill incl VAT",
    ]
].sort_values(by=["scenario", "AnnualConsumptionProfile"])

# Create new column for bill change from baseline
baseline = scenarios_summary_chart[
    scenarios_summary_chart["scenario"] == "1. Baseline"
].set_index("AnnualConsumptionProfile")["total bill incl VAT"]

scenarios_summary_chart["Bill change from baseline"] = scenarios_summary_chart.apply(
    lambda row: row["total bill incl VAT"]
    - baseline.get(row["AnnualConsumptionProfile"], 0),
    axis=1,
)

scenarios_summary_chart = scenarios_summary_chart.reset_index(drop=True)

# %% [markdown]
# **Alternative scenario with modified WHD levy object (double revenue)**

# %%
# Annex 4 and initialise alternative levies
fileobject = download_annex_4(as_fileobject=True)
double_whd_levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=24_503_683),
    WHD.from_dataframe(process_data_WHD(fileobject)),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(process_data_FIT(fileobject), revenue=689_233_317),
]
fileobject.close()

# %%
# Rebalance baseline to reflect denominators
status_quo = {}  # Recreating status quo
for levy in double_whd_levies:
    status_quo[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

# manually update WHD weights according to denominator balance
status_quo["whd"]["new_electricity_weight"] = round(
    (
        denominators["whd"]["customers_elec"]
        / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"])
    ),
    2,
)
status_quo["whd"]["new_gas_weight"] = round(
    (
        denominators["whd"]["customers_gas"]
        / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"])
    ),
    2,
)

# rebalance baseline levies
double_whd_levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in double_whd_levies
]

# %%
# Double WHD revenue
double_whd_levies[3].revenue = double_whd_levies[3].revenue * 2

# %%
# Rebalancing scenario 6: double WHD, full removal on electricity
double_whd_electricity_removal_weights = {}

for levy in double_whd_levies:
    double_whd_electricity_removal_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

for removed_levy in ["ro", "aahedc", "whd", "eco", "fit"]:
    double_whd_electricity_removal_weights[removed_levy]["new_tax_weight"] = (
        double_whd_electricity_removal_weights[removed_levy]["new_electricity_weight"]
    )
    double_whd_electricity_removal_weights[removed_levy]["new_electricity_weight"] = 0
    double_whd_electricity_removal_weights[removed_levy]["new_variable_weight_elec"] = 0
    double_whd_electricity_removal_weights[removed_levy]["new_fixed_weight_elec"] = 0

# %%
# Rebalancing scenario 7: double WHD, full rebalancing to gas
double_whd_all_gas_weights = {}

for levy in double_whd_levies:
    double_whd_all_gas_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": (
            levy.gas_variable_weight
            if levy.gas_variable_weight != 0
            else levy.electricity_variable_weight
        ),
        "new_fixed_weight_gas": (
            levy.gas_fixed_weight
            if levy.gas_fixed_weight != 0
            else levy.electricity_fixed_weight
        ),
    }

# %%
# Define all rebalancing weights for all scenarios
alternative_scenario_weights = {
    "6. Double WHD and remove all electricity": double_whd_electricity_removal_weights,
    "7. Double WHD and rebalance all electricity to gas": double_whd_all_gas_weights,
}

alternative_weights = {}
for scenario_name in alternative_scenario_weights.keys():
    alternative_weights[scenario_name] = alternative_scenario_weights.get(scenario_name)

# %%
# Electricity bills
alternative_elec_bills = {
    "baseline": ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
}

for scenario_name in alternative_scenario_weights.keys():
    alternative_elec_bills[scenario_name] = ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    )

# Gas bills
alternative_gas_bills = {
    "baseline": GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
}
for scenario_name in alternative_scenario_weights.keys():
    alternative_gas_bills[scenario_name] = GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    )

# Update baseline bill policy costs to match denominator adjusted policy costs.
alternative_elec_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, True, False) for levy in levies]
)
alternative_elec_bills["baseline"].pc = sum(
    [levy.calculate_levy(1, 0, False, False) for levy in levies]
)
alternative_gas_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, False, True) for levy in levies]
)
alternative_gas_bills["baseline"].pc = sum(
    [levy.calculate_levy(0, 1, False, False) for levy in levies]
)

# %%
# Generate scenario outputs
alternative_scenario_outputs = process_rebalancing_scenarios(
    double_whd_levies,
    alternative_weights,
    denominators,
    ofgem_archetypes_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    ["fixed", "variable", "total"],
    1_000,
)

alternative_scenario_bill_outputs = process_rebalancing_scenario_bills(
    alternative_elec_bills,
    alternative_gas_bills,
    double_whd_levies,
    alternative_weights,
    denominators,
    ofgem_archetypes_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    1_000,
    True,
)

alternative_scenario_outputs = pd.concat(
    [alternative_scenario_outputs, alternative_scenario_bill_outputs]
)

# %%
# Reshaping to recreate Martina's table for the summary chart
alternative_scenario_outputs["scenario"] = alternative_scenario_outputs[
    "scenario"
].replace("Baseline", "1. Baseline")

alternative_scenarios_summary_chart = alternative_scenario_outputs.pivot_table(
    index=[
        "AnnualConsumptionProfile",
        "scenario",
    ],
    columns="variable",
    values="value",
    aggfunc="sum",
).reset_index()

alternative_scenarios_summary_chart = alternative_scenarios_summary_chart[
    [
        "AnnualConsumptionProfile",
        "scenario",
        "ArchetypeHeatingFuel",
        "ArchetypeSize",
        "total bill incl VAT",
    ]
].sort_values(by=["scenario", "AnnualConsumptionProfile"])

alternative_scenarios_summary_chart = alternative_scenarios_summary_chart.reset_index(
    drop=True
)

# %%
# Need to have different bill values for WHD eligible and ineligible households

# Current table is for ineligible households
alternative_scenarios_summary_chart["WHD Eligibility"] = "Ineligible"

# Add column for number of eligible households
eligibility_size = ofgem_archetypes_scheme_eligibility()
whd_eligibility_size = eligibility_size[
    ["AnnualConsumptionProfile", "WHDEligibleSize"]
].set_index("AnnualConsumptionProfile")
alternative_scenarios_summary_chart["WHD Eligibility Size"] = (
    alternative_scenarios_summary_chart.apply(
        lambda row: (
            whd_eligibility_size.loc[row["AnnualConsumptionProfile"], "WHDEligibleSize"]
            if row["AnnualConsumptionProfile"] in whd_eligibility_size.index
            else 0
        ),
        axis=1,
    )
)
# Add column for number of ineligible households
alternative_scenarios_summary_chart["WHD Ineligibility Size"] = (
    alternative_scenarios_summary_chart["ArchetypeSize"]
    - alternative_scenarios_summary_chart["WHD Eligibility Size"]
)

# %%
# Create a new dataframe for eligible households to append
eligible_alternative_scenarios_summary_chart = alternative_scenarios_summary_chart.copy(
    deep=True
)

# Drop Baseline scenario rows
eligible_alternative_scenarios_summary_chart = (
    eligible_alternative_scenarios_summary_chart[
        ~eligible_alternative_scenarios_summary_chart["scenario"].str.contains(
            "1. Baseline", na=False
        )
    ]
)

# Re-classify as eligible
eligible_alternative_scenarios_summary_chart["WHD Eligibility"] = (
    eligible_alternative_scenarios_summary_chart["WHD Eligibility"].replace(
        "Ineligible", "Eligible"
    )
)

# Apply £150 + £150 rebate to eligible households
eligible_alternative_scenarios_summary_chart["total bill incl VAT"] = (
    eligible_alternative_scenarios_summary_chart["total bill incl VAT"] - 300
)

# %%
# Append eligible household rows to original dataframe
alternative_scenarios_summary_chart = pd.concat(
    [alternative_scenarios_summary_chart, eligible_alternative_scenarios_summary_chart]
)

# %%
# Create new column for bill change from baseline
baseline = alternative_scenarios_summary_chart[
    alternative_scenarios_summary_chart["scenario"] == "1. Baseline"
].set_index("AnnualConsumptionProfile")["total bill incl VAT"]

alternative_scenarios_summary_chart["Bill change from baseline"] = (
    alternative_scenarios_summary_chart.apply(
        lambda row: row["total bill incl VAT"]
        - baseline.get(row["AnnualConsumptionProfile"], 0),
        axis=1,
    )
)

# %% [markdown]
# **Combine all scenario results**

# %%
all_scenarios_summary_chart = pd.concat(
    [scenarios_summary_chart, alternative_scenarios_summary_chart]
)
# Remove Typical profile
all_scenarios_summary_chart = all_scenarios_summary_chart[
    ~all_scenarios_summary_chart["AnnualConsumptionProfile"].str.contains(
        "Typical", na=False
    )
]
# Remove duplicate Baseline scenario rows
mask = (all_scenarios_summary_chart["scenario"] == "1. Baseline") & (
    all_scenarios_summary_chart["WHD Eligibility"] == "Ineligible"
)
all_scenarios_summary_chart = all_scenarios_summary_chart[~mask]

# %% [markdown]
# **Electricity to gas unit cost ratios**

# %%
# Combine scenarios from scenario_weights and alternative_scenario_weights
scenarios = ["baseline"] + list(scenario_weights.keys())
alternative_scenarios = ["baseline"] + list(alternative_scenario_weights.keys())

# Calculate electricity-to-gas cost ratios for both sets of scenarios
scenario_ratios = [
    elec_bills[scenario].calculate_variable_consumption(1)
    / gas_bills[scenario].calculate_variable_consumption(1)
    for scenario in scenarios
]

alternative_scenario_ratios = [
    alternative_elec_bills[scenario].calculate_variable_consumption(1)
    / alternative_gas_bills[scenario].calculate_variable_consumption(1)
    for scenario in alternative_scenarios
]

# Combine both sets of data into a single dataframe
cost_ratio_frame = (
    pd.DataFrame(
        {
            "Scenario": scenarios + alternative_scenarios,
            "Electricity to gas unit cost ratio": scenario_ratios
            + alternative_scenario_ratios,
        }
    )
    .drop(5)
    .reset_index(drop=True)
)

# %% [markdown]
# **Total cost to gas, electricity and general taxation for each scenario**

# %%
scenarios = ["baseline"] + list(scenario_weights.keys())
cost_to_elec = [
    sum(
        (status_quo.get(levy.short_name).get("new_electricity_weight") / 100)
        * levy.revenue
        for levy in levies
    )
] + [
    sum(
        (
            scenario_weights.get(scenario)
            .get(levy.short_name)
            .get("new_electricity_weight")
            / 100
        )
        * levy.revenue
        for levy in levies
    )
    for scenario in scenario_weights.keys()
]
cost_to_gas = [
    sum(
        (status_quo.get(levy.short_name).get("new_gas_weight") / 100) * levy.revenue
        for levy in levies
    )
] + [
    sum(
        (
            scenario_weights.get(scenario).get(levy.short_name).get("new_gas_weight")
            / 100
        )
        * levy.revenue
        for levy in levies
    )
    for scenario in scenario_weights.keys()
]
cost_to_tax = [0] + [
    sum(
        (
            scenario_weights.get(scenario).get(levy.short_name).get("new_tax_weight")
            / 100
        )
        * levy.revenue
        for levy in levies
    )
    for scenario in scenario_weights.keys()
]

revenue_streams_data = {
    "Scenario": scenarios,
    "Total cost levied on electricity": cost_to_elec,
    "Total cost levied on gas": cost_to_gas,
    "Total cost to general taxation": cost_to_tax,
}
revenue_streams_df = pd.DataFrame(revenue_streams_data)

# %%
alternative_scenarios = ["baseline"] + list(alternative_scenario_weights.keys())
alternative_cost_to_elec = [
    sum(
        (status_quo.get(levy.short_name).get("new_electricity_weight") / 100)
        * levy.revenue
        for levy in double_whd_levies
    )
] + [
    sum(
        (
            alternative_scenario_weights.get(scenario)
            .get(levy.short_name)
            .get("new_electricity_weight")
            / 100
        )
        * levy.revenue
        for levy in double_whd_levies
    )
    for scenario in alternative_scenario_weights.keys()
]
alternative_cost_to_gas = [
    sum(
        (status_quo.get(levy.short_name).get("new_gas_weight") / 100) * levy.revenue
        for levy in double_whd_levies
    )
] + [
    sum(
        (
            alternative_scenario_weights.get(scenario)
            .get(levy.short_name)
            .get("new_gas_weight")
            / 100
        )
        * levy.revenue
        for levy in double_whd_levies
    )
    for scenario in alternative_scenario_weights.keys()
]
alternative_cost_to_tax = [0] + [
    sum(
        (
            alternative_scenario_weights.get(scenario)
            .get(levy.short_name)
            .get("new_tax_weight")
            / 100
        )
        * levy.revenue
        for levy in double_whd_levies
    )
    for scenario in alternative_scenario_weights.keys()
]

alternative_revenue_streams_data = {
    "Scenario": alternative_scenarios,
    "Total cost levied on electricity": alternative_cost_to_elec,
    "Total cost levied on gas": alternative_cost_to_gas,
    "Total cost to general taxation": alternative_cost_to_tax,
}
double_whd_revenue_streams_df = pd.DataFrame(alternative_revenue_streams_data)

# %%
scenarios_revenue_streams = pd.concat(
    [revenue_streams_df, double_whd_revenue_streams_df]
).reset_index(drop=True)
scenarios_revenue_streams["Scenario"] = scenarios_revenue_streams["Scenario"].replace(
    "baseline", "1. Baseline"
)
scenarios_revenue_streams["Total policy cost revenue"] = (
    scenarios_revenue_streams["Total cost levied on electricity"]
    + scenarios_revenue_streams["Total cost levied on gas"]
    + scenarios_revenue_streams["Total cost to general taxation"]
)
scenarios_revenue_streams = scenarios_revenue_streams.drop(5).reset_index(drop=True)

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
    all_scenarios_summary_chart.to_excel(
        writer, sheet_name="All scenarios summary", index=False
    )
    cost_ratio_frame.to_excel(writer, sheet_name="Scenario cost ratios", index=False)
    scenarios_revenue_streams.to_excel(
        writer, sheet_name="Scenario revenue streams", index=False
    )
