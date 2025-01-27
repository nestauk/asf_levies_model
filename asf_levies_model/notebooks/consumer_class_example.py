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
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model import config, PROJECT_DIR

from asf_levies_model.consumers import Consumer

# %% [markdown]
# **Setting up Levy and Tariff objects**

# %%
# Denominator values from Desnz subnational consumption domestic data
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

# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %%
# Initialise levies
fileobject = download_annex_4(as_fileobject=True)
levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=supply_elec),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=supply_elec),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=customers_gas),
    WHD.from_dataframe(
        process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
    ),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(
        process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
]
fileobject.close()

# %%
# Initialise tariffs (Other Payment method)
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
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

# %%
print(
    f"From Ofgem: {sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies])}"
)
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]
print(
    f"Rebalanced with our denominators: {sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies])}"
)

# %%
# Gas tariff
gas_tariff = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# Electricity tariff
electricity_tariff = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

# %%
# Update baseline bill policy costs to match denominator adjusted policy costs
gas_tariff.pc_nil = sum([levy.calculate_levy(0, 0, False, True) for levy in levies])
gas_tariff.pc = sum([levy.calculate_levy(0, 1, False, False) for levy in levies])
electricity_tariff.pc_nil = sum(
    [levy.calculate_levy(0, 0, True, False) for levy in levies]
)
electricity_tariff.pc = sum(
    [levy.calculate_levy(1, 0, False, False) for levy in levies]
)

# %% [markdown]
# **Setting up a Consumer object**

# %% [markdown]
# * We have `gas_tariff` and `electricity_tariff` objects that can be used to calculate the energy spend for a given consumer.
# * We can use the standing charge and unit cost rates to calculate a bill for a single energy consumer.

# %%
# Create a 'typical' consumer
typical = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=False,
)

# %% [markdown]
# There is a method to apply an adjustment to the final electricity or gas bill.

# %% [markdown]
# **Adjustment mode 1: Flat rebate**
# * This mode substracts the specified discount value from the total fuel bill.

# %%
# Check the subtotal bill for a typical consumer (this is the bill calculated based only on consumption)
typical.electricity_subtotal_bill, typical.gas_subtotal_bill

# %%
# Check the final bill before applying support
typical.electricity_bill, typical.gas_bill, typical.combined_fuel_bill

# %%
# Evaluate a flat support rate of £150 to electricity bills
if typical.scheme_eligible:
    typical = typical.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
# Get final bill
# In this case there is no adjustment to the final bill as the consumer is not scheme eligible.
typical.electricity_bill, typical.gas_bill, typical.combined_fuel_bill

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# %%
# Check the subtotal bill for a typical consumer (this is the bill before support)
# same as typical consumer
typical_eligible.electricity_subtotal_bill, typical.gas_subtotal_bill

# %%
# Evaluate a flat support rate of £150 to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
# Get final bill
# In this case there is an adjustment to the electricity bill
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# Applying multiple flat rebates

# %%
# Apply another £150 discount to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
# Get final bill
# In this case there is an £150 + £150 adjustment
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# **Adjustment mode 2: Percentage discount**
# * This mode subtracts a discount value (= percentage (%) of the *subtotal fuel bill*) from the total fuel bill.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# %%
# Evaluate a percentage discount support rate of 15% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=15,
        adjustment_mode="percentage discount",
    )

# %%
# Get final bill
# In this case there is an adjustment to the electricity bill
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
# Verifying a 15% discount was applied
typical_eligible.electricity_subtotal_bill - (
    0.15 * typical_eligible.electricity_subtotal_bill
)

# %% [markdown]
# Applying another 10% discount on top

# %%
# Evaluate a percentage discount support rate of 10% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# %%
# Get new final bill
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
# Verifying that a 10% discount AND a 15% discount was applied
(
    typical_eligible.electricity_subtotal_bill
    - (0.15 * typical_eligible.electricity_subtotal_bill)
    - (0.10 * typical_eligible.electricity_subtotal_bill)
)

# %% [markdown]
# **Adjustment mode: Unit discount**
# * This mode subtracts a discount value = unit discount (£/MWh) * fuel consumption (MWh) from the total fuel bill.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# %%
# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# Get final bill
# In this case there is an adjustment to the electricity bill.
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
# Verifying discount
typical_eligible.electricity_subtotal_bill - (typical.electricity_consumption * 50)

# %% [markdown]
# Applying an additional 50 £/MWh unit discount

# %%
# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# Get final bill
# In this case there is an adjustment to the electricity bill.
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %%
# Verifying discount
(
    typical_eligible.electricity_subtotal_bill
    - (typical.electricity_consumption * 50)
    - (typical.electricity_consumption * 50)
)

# %% [markdown]
# **Adjustment mode: Rising block discount**
# * This mode calculates discount based on varying unit discount rates for specific blocks of consumption units, and subtracts that discount from the total fuel bill.

# %%
# Create a 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=True,
)

# %% [markdown]
# Example discount structure:
# - For units of electricity below 1 MWh, apply a unit discount of 50 £/MWh
# - For units of electricity between 1-2 MWh, apply a unit discount of 30 £/MWh
# - For units of electricity between 2-3 MWh, apply a unit discount of 10 £/MWh
# - No discount applied for units of electricity above 3 MWh
#
# Note: All consumption thresholds are annual.

# %%
discount_structure = {
    "thresholds": [1, 2, 3],
    "discounts": [50, 30, 10],
}

# %%
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# %% [markdown]
# With consumption = 2.7, we expect the following discount:
# - (1 - 0) * 50 = 50
# - (2 - 1) * 30 = 30
# - (2.7 - 2) * 10 = 7
# - Total = £87 discount

# %%
# Verify discount applied
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# Applying an additional discount structure

# %%
discount_structure_additional = {
    "thresholds": [1, 2, 3],
    "discounts": [30, 20, 10],
}

# %%
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure_additional,
        adjustment_mode="rising block",
    )

# %% [markdown]
# With consumption = 2.7, we expect the following discount:
# - (1 - 0) * 30 = 30
# - (2 - 1) * 20 = 20
# - (2.7 - 2) * 10 = 7
# - Total = £57 + £87 discount from first discount structure = £144

# %%
# Verify discount applied
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# Checking that a discount structure with only 1 threshold works.

# %%
# Create a 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=True,
)

# %%
discount_structure = {
    "thresholds": [2],
    "discounts": [50],
}

# %% [markdown]
# This translates to:
# - First 2 MWh of consumption gets a discount of 50 £/MWh
# - Over 2 MWh of consumption does not get a discount
# - Total discount for 2.7 MWh electricity = 2 * 50 = £100

# %%
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# %%
# Verify discount applied
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# **Applying different adjustment modes**

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# %% [markdown]
# **Combination 1: Flat rebate + percentage discount**

# %%
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
# Verify a £150 discount applied
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# The new electricity bill for typical_eligible has now been discounted £150.

# %% [markdown]
# Let's add another layer of support: 10% discount
# * This is implemented as applying another discount that is 10% of the subtotal electricity bill (i.e. bill before the flat rebate was applied)

# %%
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# %% [markdown]
# The new electricity bill now reflects two discounts:
# * £150 discount
# * 10% of the subtotal bill

# %%
# Verify a £150 discount AND 10% discount applied
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
150 + ((10 / 100) * typical_eligible.electricity_subtotal_bill)

# %% [markdown]
# When combining flat rebate and percentage discount, the order of operations does not matter and the total discount will be the same.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Apply % discount first
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# Apply flat rebate second
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(typical_eligible.electricity_subtotal_bill * 0.1) + 150

# %% [markdown]
# **Combination 2: Flat rebate + unit discount**

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# %%
# Apply another £150 discount to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
150 + (typical_eligible.electricity_consumption * 50)

# %% [markdown]
# Order of operations also doesn't matter here.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# Apply another £150 discount to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %% [markdown]
# **Combination 3: Percentage discount + unit discount**

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Evaluate a percentage discount support rate of 10% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(typical_eligible.electricity_subtotal_bill * 0.1) + (
    typical_eligible.electricity_consumption * 50
)

# %% [markdown]
# Order of operations doesn't matter.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Evaluate a percentage discount support rate of £50/MWh (5p/kWh)
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=50,
        adjustment_mode="unit discount",
    )

# Evaluate a percentage discount support rate of 10% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(typical_eligible.electricity_consumption * 50) + (
    typical_eligible.electricity_subtotal_bill * 0.1
)

# %% [markdown]
# **Combination 4: Percentage discount + rising block unit discount**

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Evaluate a percentage discount support rate of 10% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )


# Evaluate a rising block unit discount
discount_structure = {
    "thresholds": [1, 2, 3],
    "discounts": [50, 30, 10],
}
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(typical_eligible.electricity_subtotal_bill * 0.1) + (50 + 30 + 7)

# %% [markdown]
# Order of operations doesn't matter.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Evaluate a rising block unit discount
discount_structure = {
    "thresholds": [1, 2, 3],
    "discounts": [50, 30, 10],
}
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# Evaluate a percentage discount support rate of 10% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=10,
        adjustment_mode="percentage discount",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(typical_eligible.electricity_subtotal_bill * 0.1) + (50 + 30 + 7)

# %% [markdown]
# **Combination 5: Flat rebate + rising block unit discount**

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)

# Apply another £150 discount to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )


# Evaluate a rising block unit discount
discount_structure = {
    "thresholds": [1, 2, 3],
    "discounts": [50, 30, 10],
}
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(150) + (50 + 30 + 7)

# %% [markdown]
# Order of operations also doesn't matter here.

# %%
# Create a scheme eligible 'typical' consumer
typical_eligible = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    scheme_eligible=True,
)


# Evaluate a rising block unit discount
discount_structure = {
    "thresholds": [1, 2, 3],
    "discounts": [50, 30, 10],
}
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=discount_structure,
        adjustment_mode="rising block",
    )

# Apply another £150 discount to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )

# %%
typical_eligible.electricity_subtotal_bill - typical_eligible.electricity_bill

# %%
(150) + (50 + 30 + 7)

# %% [markdown]
# **Combination 6: Unit discount + rising block unit discount**
# - This combination would not be applied as it is two forms of the same type of discount.

# %% [markdown]
# **Other calculated properties of a Consumer**

# %%
# Create a 'typical' consumer
typical = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=35_464,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

# %% [markdown]
# Fuel poverty gap calculation:
# * If % of net income spent on fuel > 10% -> fuel poverty gap = (spending on fuel) - 0.1*(net annual income)
# * where spending on fuel = electricity_bill + gas_bill + unmetered_fuel_spend
# * This gap value is a calculated property

# %%
typical.fuel_poverty_gap

# %% [markdown]
# Gap is zero because fuel spending is not above 10% of the household's net income

# %%
(typical.combined_fuel_bill + typical.unmetered_fuel_spend) - (
    typical.net_annual_income * 0.1
)

# %% [markdown]
# Let's test that it works for a household that should have a non-zero fuel poverty gap

# %%
dummy = Consumer(
    name="Typical",
    archetype=None,
    net_annual_income=20_000,
    net_income_decile=5,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=400,
    scheme_eligible=False,
)

# %%
dummy.fuel_poverty_gap

# %%
(dummy.combined_fuel_bill + dummy.unmetered_fuel_spend) - (
    dummy.net_annual_income * 0.1
)

# %% [markdown]
# Savings in running costs if switching from gas boiler to electric heat pump

# %%
typical.boiler_to_hp_savings()  # with default assumptions

# %% [markdown]
# Creating a summary dataframe

# %%
typical.get_tidy_summary()
