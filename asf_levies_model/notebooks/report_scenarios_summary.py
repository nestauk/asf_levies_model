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
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.summary import (
    process_rebalancing_scenarios,
    process_rebalancing_scenario_bills,
)

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
    "Remove all electricity": sq_electricity_removal_weights,
    "Remove RO and FIT": remove_ro_fit_weights,
    "Rebalance all electricity to gas": sq_all_gas_weights,
    "Rebalance RO and FIT to gas": rebalance_ro_fit_weights,
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
scenario_outputs

# %%
# Total cost moved to general taxation
scenarios = ["baseline"] + list(scenario_weights.keys())
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

cost_to_tax_data = {
    "Scenario": scenarios,
    "Total cost to general taxation": cost_to_tax,
}
cost_to_tax_df = pd.DataFrame(cost_to_tax_data)

cost_to_tax_df

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
alternative_scenario_weights = {
    "Double WHD and remove all electricity": double_whd_electricity_removal_weights,
    "Double WHD and rebalance all electricity to gas": double_whd_all_gas_weights,
}

alternative_weights = {}
for scenario_name in alternative_scenario_weights.keys():
    alternative_weights[scenario_name] = alternative_scenario_weights.get(scenario_name)

# %%
# Create bill objects
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
### TO DO: Introduce rebates targeting to apply double WHD subsidy to eligible households and get final bill results

# %%
# Total cost moved to general taxation
alternative_scenarios = ["baseline"] + list(alternative_scenario_weights.keys())
cost_to_tax = [0] + [
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

cost_to_tax_data = {
    "Scenario": alternative_scenarios,
    "Total cost to general taxation": cost_to_tax,
}
double_whd_cost_to_tax_df = pd.DataFrame(cost_to_tax_data)

double_whd_cost_to_tax_df

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

# %%
cost_ratio_frame

# %%
