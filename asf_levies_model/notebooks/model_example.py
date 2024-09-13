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
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import (
    ElectricityStandardCredit,
    GasStandardCredit,
    ElectricityOtherPayment,
    GasOtherPayment,
    ElectricityPPM,
    GasPPM,
)

# %% [markdown]
# ### Policy Costs

# %%
# Example downloading annex 4
url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_4_-_Policy_cost_allowance_methodology_v1.19%20%281%29.xlsx"
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
        process_data_FIT()
    ),  # defaults to a total consumption denominator, so needs changes to reflect domestic share.
]


# %%
# get sum of policy costs for typical consumption
sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies])

# %%
# deonminators from subnational consumption estimates

"""
# Most appropraite total or domestic denominator
denominators = {'ro': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'aahedc': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'ggl': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600},
                'whd': {'supply_elec':94_200_366, 'supply_gas':265_197_947, 'customers_gas':24_503_683,  'customers_elec':29_078_770},
                'eco': {'supply_elec':94_200_366, 'supply_gas':265_197_947, 'customers_gas':24_503_683,  'customers_elec':29_078_770},
                'fit': {'supply_elec':250_020_739, 'supply_gas':435_369_123, 'customers_gas':24_750_358,  'customers_elec':31_537_600}}
"""

# Using just domestic values for rebalancing
denominators = {
    "ro": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
    "aahedc": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
    "ggl": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
    "whd": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
    "eco": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
    "fit": {
        "supply_elec": 94_200_366,
        "supply_gas": 265_197_947,
        "customers_gas": 24_503_683,
        "customers_elec": 29_078_770,
    },
}

# %%
# rebalance
rebalance_electricity_variable = {
    "new_electricity_weight": 1,
    "new_gas_weight": 0,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 1,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

elec_var_levies = [
    levy.rebalance_levy(
        **rebalance_electricity_variable, **denominators[levy.short_name]
    )
    for levy in levies
]

# %%
# get sum of new policy costs
sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in elec_var_levies])

# %%
# rebalance
rebalance_gas_variable = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

gas_var_levies = [
    levy.rebalance_levy(**rebalance_gas_variable, **denominators[levy.short_name])
    for levy in levies
]

# %%
# get sum of new policy costs
sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in gas_var_levies])

# %%
# rebalance
rebalance_electricity_fixed = {
    "new_electricity_weight": 1,
    "new_gas_weight": 0,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 1,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 0,
}

elec_fixed_levies = [
    levy.rebalance_levy(**rebalance_electricity_fixed, **denominators[levy.short_name])
    for levy in levies
]

# %%
# get sum of new policy costs
sum([levy.calculate_levy(4.684, 18.53, True, True) for levy in elec_fixed_levies])

# %%
# rebalance
rebalance_gas_fixed = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 0,
    "new_fixed_weight_gas": 1,
}

gas_fixed_levies = [
    levy.rebalance_levy(**rebalance_gas_fixed, **denominators[levy.short_name])
    for levy in levies
]

# %%
# get sum of new policy costs
sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in gas_fixed_levies])

# %% [markdown]
# ### Bill Costs

# %%
# Getting annex 9

url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_9_-_Levelisation_allowance_methodology_and_levelised_cap_levels_v1.3.xlsx"
download_annex_9(url)

# %% [markdown]
# #### Standard Credit

# %% [markdown]
# ##### Electricity

# %%
elec_standard_credit_nil = process_tariff_elec_standard_credit_nil()
elec_standard_credit_typical = process_tariff_elec_standard_credit_typical()

# %%
# Create a tariff object
elec_bill = ElectricityStandardCredit.from_dataframe(
    elec_standard_credit_nil, elec_standard_credit_typical
)

# %%
# This is the bill with default values.
elec_bill.calculate_total_consumption(2.7)

# %%
# In theory we can update the pc_nil and pc attributes with relevant costs.
# Let's use the defaults and check it works!

elec_bill.pc_nil = sum([levy.calculate_fixed_levy(True, False) for levy in levies])
elec_bill.pc = sum([levy.calculate_variable_levy(1, 0) for levy in levies])

# %%
# Now recalculate - there's a 10p difference, which comes from variable costs - rounding?
elec_bill.calculate_total_consumption(2.7)

# %% [markdown]
# ##### Gas

# %%
gas_standard_credit_nil = process_tariff_gas_standard_credit_nil()
gas_standard_credit_typical = process_tariff_gas_standard_credit_typical()

# %%
# Create
gas_bill = GasStandardCredit.from_dataframe(
    gas_standard_credit_nil, gas_standard_credit_typical
)

# %%
# This is the bill with default values.
gas_bill.calculate_total_consumption(11.5)

# %%
# Let's use the defaults and check it works!

gas_bill.pc_nil = sum([levy.calculate_fixed_levy(False, True) for levy in levies])
gas_bill.pc = sum([levy.calculate_variable_levy(0, 1) for levy in levies])

# %%
# Check it works - its the same!
gas_bill.calculate_total_consumption(11.5)

# %% [markdown]
# #### Other Payment Method

# %% [markdown]
# ##### Electricity

# %%
elec_other_payment_nil = process_tariff_elec_other_payment_nil()
elec_other_payment_typical = process_tariff_elec_other_payment_typical()

# %%
# Create a tariff object
elec_bill = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

# %%
# This is the bill with default values.
elec_bill.calculate_total_consumption(2.7)

# %% [markdown]
# ##### Gas

# %%
gas_other_payment_nil = process_tariff_gas_other_payment_nil()
gas_other_payment_typical = process_tariff_gas_other_payment_typical()

# %%
# Create
gas_bill = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# %%
# This is the bill with default values.
gas_bill.calculate_total_consumption(11.5)

# %% [markdown]
# #### PPM

# %% [markdown]
# ##### Electricity

# %%
elec_ppm_nil = process_tariff_elec_ppm_nil()
elec_ppm_typical = process_tariff_elec_ppm_typical()

# %%
# Create a tariff object
elec_bill = ElectricityPPM.from_dataframe(elec_ppm_nil, elec_ppm_typical)

# %%
# This is the bill with default values.
elec_bill.calculate_total_consumption(2.7)

# %% [markdown]
# ##### Gas

# %%
gas_ppm_nil = process_tariff_gas_ppm_nil()
gas_ppm_typical = process_tariff_gas_ppm_typical()

# %%
# Create
gas_bill = GasPPM.from_dataframe(gas_ppm_nil, gas_ppm_typical)

# %%
# This is the bill with default values.
gas_bill.calculate_total_consumption(11.5)
