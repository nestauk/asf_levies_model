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

from asf_levies_model.tariffs import (
    ElectricityStandardCredit,
    GasStandardCredit,
    ElectricityOtherPayment,
    GasOtherPayment,
    ElectricityPPM,
    GasPPM,
)

# %% [markdown]
# Extracting tariff cost components: Other Payment method

# %%
# Getting annex 9
url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_9_-_Levelisation_allowance_methodology_and_levelised_cap_levels_v1.3.xlsx"
download_annex_9(url)

# %%
# Create electricity bill object
elec_other_payment_nil = process_tariff_elec_other_payment_nil()
elec_other_payment_typical = process_tariff_elec_other_payment_typical()
elec_bill = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)
# Create gas bill object
gas_other_payment_nil = process_tariff_gas_other_payment_nil()
gas_other_payment_typical = process_tariff_gas_other_payment_typical()
gas_bill = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# %% [markdown]
# **Electricity and gas unit costs refer only to the variable costs.**

# %%
elec_bill.calculate_variable_consumption(1) / gas_bill.calculate_variable_consumption(1)

# %% [markdown]
# If policy costs are the only thing we can change, then minimising the ratio means:
# - Making electricity variable charges as low as possible (this could also mean moving all electricity policy costs to fixed charges)
# - Making gas variable charges as high as possible
#
# This means the lowest ratio achievable is through charging policy costs on gas units.

# %% [markdown]
# ---

# %% [markdown]
# Checking domestic denominator values with number of households reported with Ofgem archetypes

# %%
# Subnational accounts, domestic
supply_elec = 94_200_366
supply_gas = 265_197_947
customers_gas = 24_503_683
customers_elec = 29_078_770

# %%
archetype_data = ofgem_archetypes_data()

# %% [markdown]
# Number of gas households

# %%
gas_households = archetype_data.loc[
    archetype_data["GaskWh"] != 0, "ArchetypeSize"
].sum()
gas_households, customers_gas

# %%
elec_households = archetype_data.loc[
    archetype_data["ElectricitySingleRatekWh"] != 0, "ArchetypeSize"
].sum()
elec_households, customers_elec

# %% [markdown]
# ---
# *Ignore below (not correct way of calculating electricity:gas price ratio)*

# %% [markdown]
# With current policy costs (status quo levy rates)

# %%
archetype_data = ofgem_archetypes_data()

# %%
archetype_data["Electricity bill"] = elec_bill.calculate_total_consumption(
    archetype_data["ElectricitySingleRatekWh"] / 1_000, vat=True
)
archetype_data["Gas bill"] = gas_bill.calculate_total_consumption(
    archetype_data["GaskWh"] / 1_000, vat=True
)
archetype_data["Electricity unit cost"] = (
    archetype_data["Electricity bill"] / archetype_data["ElectricitySingleRatekWh"]
)
archetype_data["Gas unit cost"] = archetype_data["Gas bill"] / archetype_data["GaskWh"]
archetype_data["Electricity to gas price ratio"] = (
    archetype_data["Electricity unit cost"] / archetype_data["Gas unit cost"]
)

archetype_data

# %%
archetype_data.loc[
    :,
    [
        "AnnualConsumptionProfile",
        "Electricity unit cost",
        "Gas unit cost",
        "Electricity to gas price ratio",
    ],
]

# %% [markdown]
# ### What is the theoretical minimum ratio that is possible for a given consumption profile (if we're only able to change policy costs)?
# - Ratio = (Electricity bill/Electricity consumption) / (Gas bill/Gas consumption)
# - We want to make the numerator as small as possible and denominator as big as possible
# - Electricity policy costs = 0
# - Gas policy costs -> which one of fixed vs variable charges makes this bigger?

# %%
# Define constants
DOMESTIC_CUSTOMERS_ELEC = 29_078_770  # customers
DOMESTIC_CUSTOMERS_GAS = 24_503_683  # customers
DOMESTIC_SUPPLY_ELEC = 94_200_366  # MWh
DOMESTIC_SUPPLY_GAS = 265_197_947  # MWh

REVENUE_GGL = 0.38325 * DOMESTIC_CUSTOMERS_GAS
REVENUE_WHD = 553_000_000
REVENUE_AAHEDC = 0.42145 * DOMESTIC_SUPPLY_ELEC
REVENUE_ECO = 1_435_000_000
REVENUE_RO = 31.78 * DOMESTIC_SUPPLY_ELEC
REVENUE_FIT = 689_233_317  # domestic share based on domestic electricity supply/total eligible supply

# %%
# Take a basis of a theoretical revenue
revenue = 1_000_000

# What is the policy cost to a typical consumer if charging base is customers (fixed levy rate)
levy_fixed = revenue / DOMESTIC_CUSTOMERS_GAS
policy_cost_fixed = levy_fixed

# What is the policy cost to a typical consumer if charging base is gas units (variable levy rate)
levy_variable = revenue / DOMESTIC_SUPPLY_GAS
policy_cost_variable = levy_variable * 11.5

print(policy_cost_fixed, policy_cost_variable)

# %% [markdown]
# **For a given policy scheme, the largest gas policy cost arises when the levy charging base is gas units.**<br>
# Let's calculate the theoretical "floor" of the electricity to gas price ratio.

# %%
# Example downloading annex 4
url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_4_-_Policy_cost_allowance_methodology_v1.19%20%281%29.xlsx"
download_annex_4(url)

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

# Rebalancing to 100% gas variable
weights = {
    "new_electricity_weight": 0,
    "new_gas_weight": 1,
    "new_tax_weight": 0,
    "new_variable_weight_elec": 0,
    "new_fixed_weight_elec": 0,
    "new_variable_weight_gas": 1,
    "new_fixed_weight_gas": 0,
}

# %%
# Rebalance
gas_var_levies = [
    levy.rebalance_levy(**weights, **denominators[levy.short_name]) for levy in levies
]

# %%
# Create new instance of electricity bill (theoretical)
elec_bill_theoretical = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

# Update policy costs in bill
elec_bill_theoretical.pc_nil = sum(
    [levy.calculate_fixed_levy(True, False) for levy in gas_var_levies]
)
elec_bill_theoretical.pc = sum(
    [levy.calculate_variable_levy(1, 0) for levy in gas_var_levies]
)

elec_pc_theoretical = (
    elec_bill_theoretical.pc_nil - elec_bill_theoretical.pc * 2.7
) * 1.05

elec_pc_theoretical

# %% [markdown]
# How to make gas policy costs as big as possible?

# %%
# Create new instance of gas bill (theoretical)
gas_bill_theoretical = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# %%
# Update gas policy costs
gas_bill_theoretical.pc_nil = sum(
    [levy.calculate_fixed_levy(False, True) for levy in gas_var_levies]
)
gas_bill_theoretical.pc = sum(
    [levy.calculate_variable_levy(0, 1) for levy in gas_var_levies]
)
gas_pc_theoretical = (
    gas_bill_theoretical.pc_nil + (gas_bill_theoretical.pc * 11.5)
) * 1.05

gas_pc_theoretical

# %%
# Increase in policy costs (should be the same as increase in total bill)
gas_pc = (gas_bill.pc_nil + gas_bill.pc * 11.5) * 1.05
gas_pc_theoretical - gas_pc

# %%
# Compare current vs. theoretical gas bill cost
gas_bill_cost = gas_bill.calculate_total_consumption(11.5, vat=True)
gas_bill_cost_theoretical = gas_bill_theoretical.calculate_total_consumption(
    11.5, vat=True
)
gas_bill_cost, gas_bill_cost_theoretical, gas_bill_cost_theoretical - gas_bill_cost

# %%
# Compare current vs. theoretical electricity bill cost
elec_bill_cost = elec_bill.calculate_total_consumption(2.7, vat=True)

elec_bill_cost_theoretical = elec_bill_theoretical.calculate_total_consumption(
    2.7, vat=True
)
elec_bill_cost, elec_bill_cost_theoretical, elec_bill_cost_theoretical - elec_bill_cost

# %%
# Compare current vs. theoretical total bill
total_bill_cost = elec_bill_cost + gas_bill_cost
total_bill_cost_theoretical = elec_bill_cost_theoretical + gas_bill_cost_theoretical
total_bill_cost, total_bill_cost_theoretical, total_bill_cost_theoretical - total_bill_cost

# %%
# New fuel bills
elec_bill_cost_theoretical, gas_bill_cost_theoretical

# %%
# New unit costs
elec_bill_cost_theoretical / 2700, gas_bill_cost_theoretical / 11500

# %%
# New price ratio
theoretical_min_ratio = (elec_bill_cost_theoretical / 2.7) / (
    gas_bill_cost_theoretical / 11.5
)
theoretical_min_ratio

# %%
# Required bill increase
total_bill_cost_theoretical - total_bill_cost

# %% [markdown]
# **The theoretical "floor" of the electricity-to-gas price ratio (if we can only change policy costs and not any other tariff components) is 3.00. This corresponds to a £64.30 increase in the energy bill of a typical consumer**
# - This is in line with the set of results we see in the optimisation model.

# %% [markdown]
#
