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
    ofgem_archetypes_scheme_eligibility,
    ofgem_archetypes_equivalised_income_deciles,
    ofgem_archetypes_net_income_deciles,
    ofgem_archetypes_retired_pension,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.summary import (
    process_rebalancing_scenarios,
    process_rebalancing_scenario_bills,
    subsidisation_table,
    transform_income_decile_eligibility,
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
# Rebalance baseline to reflect denominators
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
status_quo["whd"]["new_electricity_weight"] = denominators["whd"]["customers_elec"] / (
    denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]
)
status_quo["whd"]["new_gas_weight"] = denominators["whd"]["customers_gas"] / (
    denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]
)

# rebalance baseline levies
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# %%
# Set scenario and rebalancing weights
scenario_name = "100% gas, variable"

gas_variable_weights = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

weights = {
    scenario_name: {
        key: gas_variable_weights
        for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
    },
}

# %%
# Create bill objects
elec_bills = {
    "baseline": ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
    scenario_name: ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
}
gas_bills = {
    "baseline": GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
    scenario_name: GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
}

# Update baseline bill policy costs to match denominator adjusted policy costs.
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

# %%
scenario_outputs = pd.concat([scenario_outputs, scenario_bill_outputs])

# %% [markdown]
# **Generating dataframe of new bills**

# %%
# Criteria from scheme eligibility table
subsidisation_table(
    scenario_outputs,
    scenario_name,
    rebate=150,
    eligibility_criteria="ECO",
    eligibility_dataframe=ofgem_archetypes_scheme_eligibility(),
    ineligible_households_pay=False,
)

# %%
# Criteria from retired/pension recipient table
subsidisation_table(
    scenario_outputs,
    scenario_name,
    rebate=150,
    eligibility_criteria="Retired Economic Status",
    eligibility_dataframe=ofgem_archetypes_retired_pension(),
    ineligible_households_pay=False,
)

# %%
# Criteria from income decile table
subsidisation_table(
    scenario_outputs,
    scenario_name,
    rebate=150,
    eligibility_criteria="Income Deciles",
    eligibility_dataframe=transform_income_decile_eligibility(
        ofgem_archetypes_equivalised_income_deciles(), eligible_deciles=4
    ),
    eligible_deciles=4,
    ineligible_households_pay=False,
)

# %%
