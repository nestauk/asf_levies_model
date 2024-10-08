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
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
    download_annex_9,
    process_tariff_elec_standard_credit_nil,
    process_tariff_elec_standard_credit_typical,
    process_tariff_gas_standard_credit_nil,
    process_tariff_gas_standard_credit_typical,
    process_tariff_elec_other_payment_nil,
    process_tariff_elec_other_payment_typical,
    process_tariff_gas_other_payment_nil,
    process_tariff_gas_other_payment_typical,
    process_tariff_elec_ppm_nil,
    process_tariff_elec_ppm_typical,
    process_tariff_gas_ppm_nil,
    process_tariff_gas_ppm_typical,
    ofgem_archetypes_data,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.summary import (
    process_rebalancing_scenarios,
    process_rebalancing_scenario_bills,
)

from asf_levies_model.tariffs import (
    ElectricityStandardCredit,
    GasStandardCredit,
    ElectricityOtherPayment,
    GasOtherPayment,
    ElectricityPPM,
    GasPPM,
)

# %%
# Example downloading annex 4
# url = "https://www.ofgem.gov.uk/sites/default/files/2024-03/Annex_4_-_Policy_cost_allowance_methodology_v1.18.xlsx"
url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_4_-_Policy_cost_allowance_methodology_v1.19 (1).xlsx"
download_annex_4(url)

# %%
# Initialise the existing levies
levies = [
    RO.from_dataframe(
        process_data_RO(), denominator=94_200_366
    ),  # domestic denominator
    AAHEDC.from_dataframe(
        process_data_AAHEDC(), denominator=94_200_366
    ),  # domestic denominator
    GGL.from_dataframe(
        process_data_GGL(), denominator=24_503_683
    ),  # domestic denominator
    WHD.from_dataframe(process_data_WHD()),  # domestic only levy
    ECO.from_dataframe(process_data_ECO()),  # domestic only levy
    FIT.from_dataframe(
        process_data_FIT(),
        revenue=689_233_317,  # This revenue is the domestic share based on domestic electricity supply/total elligible supply.
    ),
]

# %%
# deonminators from subnational consumption estimates

"""
# Most appropriate total or domestic denominator
denominators = {'ro': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'aahedc': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'ggl': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'whd': {'supply_elec':94_200_366, 'supply_gas':265_197_947, 'customers_gas':24_503_683,  'customers_elec':29_078_770},
                'eco': {'supply_elec':94_200_366, 'supply_gas':265_197_947, 'customers_gas':24_503_683,  'customers_elec':29_078_770},
                'fit': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600}}
"""

# Using just domestic values for rebalancing
domestic_values = {
    "supply_elec": 94_200_366,
    "supply_gas": 265_197_947,
    "customers_gas": 24_503_683,
    "customers_elec": 29_078_770,
}

denominators = {
    key: domestic_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}

# %%
# Annual consumption profiles
consumption_values_df = pd.concat(
    [
        pd.Series(
            [
                "Typical",
                "A1",
                "A2",
                "A3",
                "B4",
                "B5",
                "B6",
                "C7",
                "C8",
                "C9",
                "D10",
                "D11",
                "D12",
                "E13",
                "E14",
                "F15",
                "F16",
                "G17",
                "G18",
                "H19",
                "H20",
                "I21",
                "I22",
                "J23",
                "J24",
            ],
            name="AnnualConsumptionProfile",
        ),
        pd.Series(
            [
                2700.0,
                2742.0,
                2849.0,
                3519.0,
                4811.0,
                6597.0,
                3028.0,
                3649.0,
                5587.0,
                3337.0,
                3881.0,
                2482.0,
                3952.0,
                5075.0,
                4070.0,
                6883.0,
                4317.0,
                5901.0,
                5294.0,
                4907.0,
                3143.0,
                4070.0,
                4684.0,
                4532.0,
                7523.0,
            ],
            name="ElectricitySingleRatekWh",
        ),
        pd.Series(
            [
                11500.0,
                10933.0,
                9464.0,
                10622.0,
                0.0,
                0.0,
                10525.0,
                13119.0,
                0.0,
                13685.0,
                13981.0,
                8782.0,
                16065.0,
                16722.0,
                14606.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                11677.0,
                15461.0,
                18530.0,
                16330.0,
                0.0,
            ],
            name="GaskWh",
        ),
    ],
    axis=1,
)

# %%
electricity_variable_weights = {
    "new_electricity_weight": 1,
    "new_gas_weight": 0,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

electricity_fixed_weights = {
    "new_electricity_weight": 1,
    "new_gas_weight": 0,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 1,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

gas_variable_weights = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

gas_fixed_weights = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 1,
}

weights = {
    "100% Electricity Variable": {
        key: electricity_variable_weights
        for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
    },
    "100% Electricity Fixed": {
        key: electricity_fixed_weights
        for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
    },
    "100% Gas Variable": {
        key: gas_variable_weights
        for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
    },
    "100% Gas Fixed": {
        key: gas_fixed_weights for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
    },
}

# %%
scenario_outputs = process_rebalancing_scenarios(
    levies,
    weights,
    denominators,
    consumption_values_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    ["variable", "fixed", "total"],
    1_000,
)

# %% [markdown]
# Calculating total bills

# %%
# Getting annex 9
url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_9_-_Levelisation_allowance_methodology_and_levelised_cap_levels_v1.3.xlsx"
download_annex_9(url)

# %%
elec_other_payment_nil = process_tariff_elec_other_payment_nil()
elec_other_payment_typical = process_tariff_elec_other_payment_typical()
gas_other_payment_nil = process_tariff_gas_other_payment_nil()
gas_other_payment_typical = process_tariff_gas_other_payment_typical()

# %%
# Initialise bills
elec_bills = {
    "baseline": ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
    "100% Gas Variable": ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    ),
}

gas_bills = {
    "baseline": GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
    "100% Gas Variable": GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    ),
}

# Archetypes
archetype_data = ofgem_archetypes_data()

# %%
scenario_bill_outputs = process_rebalancing_scenario_bills(
    elec_bills,
    gas_bills,
    levies,
    weights,
    denominators,
    archetype_data,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    1_000,
    True,
)
scenario_bill_outputs

# %%
pd.concat([scenario_outputs, scenario_bill_outputs])

# %%
