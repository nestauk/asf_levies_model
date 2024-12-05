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

# %% [markdown]
# Setting up status quo levies and tariffs.

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

# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Annex 4 and initialise levies
fileobject = download_annex_4(as_fileobject=True)
levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=24_503_683),
    WHD.from_dataframe(process_data_WHD(fileobject)),
    ECO.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(
        process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
]
fileobject.close()

# Annex 9 and initialise tariffs (Other Payment method)
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# Status quo - Rebalance baseline to reflect denominators
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
# Gas tariff
gas_tariff = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# Electricity tariff
electricity_tariff = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

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
# * We have `gas_tariff` and `electricity_tariff` objects that can be used to calculate the energy spend for a given consumer.
# * We can use the standing charge and unit cost rates to calculate a bill for a single energy consumer.

# %%
from asf_levies_model.consumers import Consumer

# %%
dummy_household = Consumer(
    name="Dummy",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

# %% [markdown]
# Electricity and gas bill values are instance attributes.

# %%
dummy_household.electricity_bill

# %% [markdown]
# Fuel poverty gap calculation:
# * If % of net income spent on fuel > 10% -> fuel poverty gap = (spending on fuel) - 0.1*(net annual income)
# * This gap value is a calculated property

# %%
dummy_household.fuel_poverty_gap

# %% [markdown]
# There is a method to apply an adjustment to the final electricity or gas bill
# * Currently, adjustments are done to the subtotal bill (which is read-only and is calculated from consumption) so it is not possible to "layer" different adjustments on top of each other

# %%
dummy_household.apply_social_support_adjustment(
    adjustment_fuel="electricity",
    adjustment_parameter=-150,
    adjustment_mode="flat adjustment",
)
dummy_household.electricity_bill

# %%
dummy_household.apply_social_support_adjustment(
    adjustment_fuel="electricity",
    adjustment_parameter=15,
    adjustment_mode="percentage discount",
)
dummy_household.electricity_bill

# %%
dummy_household.apply_social_support_adjustment(
    adjustment_fuel="electricity",
    adjustment_parameter=1,
    adjustment_mode="unit discount",
)
dummy_household.electricity_bill

# %% [markdown]
# Demonstrating a way we could do a cross-subsidisation mechanism

# %%
eligible_1 = Consumer(
    name="Eligible household 1",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=True,
)

eligible_2 = Consumer(
    name="Eligible household 2",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=12,
    electricity_consumption=2,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=True,
)

ineligible_1 = Consumer(
    name="Eligible household 1",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=14,
    electricity_consumption=3,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

households = [eligible_1, eligible_2, ineligible_1]

# %%
for household in households:
    if household.scheme_eligible:
        rebate = -150
        household.apply_social_support_adjustment(
            adjustment_fuel="electricity",
            adjustment_parameter=rebate,
            adjustment_mode="flat adjustment",
        )
    else:
        support = -(
            rebate * sum(1 for x in households if x.scheme_eligible == True)
        ) / sum(1 for x in households if x.scheme_eligible == False)
        household.apply_social_support_adjustment(
            adjustment_fuel="electricity",
            adjustment_parameter=support,
            adjustment_mode="flat adjustment",
        )

# %%
eligible_1.electricity_subtotal_bill, eligible_1.electricity_bill

# %%
eligible_2.electricity_subtotal_bill, eligible_2.electricity_bill

# %%
ineligible_1.electricity_subtotal_bill, ineligible_1.electricity_bill

# %% [markdown]
# Electricity-to-gas unit cost ratio
# - The unit cost ratio is a calculated property
# - If a social support adjustment has been made via mode="unit discount" then the Consumer's unit cost ratio calculation will take the unit discount into account

# %%
dummy_household = Consumer(
    name="Dummy",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

# %%
dummy_household.unit_cost_ratio

# %%
dummy_household.apply_social_support_adjustment(
    adjustment_fuel="electricity",
    adjustment_parameter=1,
    adjustment_mode="unit discount",
)
dummy_household.electricity_bill

# %%
# Unit cost ratio is calculated considering any unit discount
dummy_household.unit_cost_ratio

# %%
dummy_household.apply_social_support_adjustment(
    adjustment_fuel="electricity",
    adjustment_parameter=-150,
    adjustment_mode="flat adjustment",
)
dummy_household.electricity_bill

# %%
# Unit cost ratio is unaffected as adjustment_mode != "unit discount"
dummy_household.unit_cost_ratio

# %% [markdown]
# Savings in running costs if switching from gas boiler to electric heat pump

# %%
dummy_household = Consumer(
    name="Dummy",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

# %%
dummy_household.boiler_to_hp_savings()  # with default assumptions

# %% [markdown]
# Creating a summary dataframe

# %%
dummy_household = Consumer(
    name="Dummy",
    archetype="A1",
    net_annual_income=10_000,
    net_income_decile=4,
    main_heating_fuel="gas",
    gas_consumption=11.5,
    electricity_consumption=2.7,
    gas_tariff=gas_tariff,
    electricity_tariff=electricity_tariff,
    unmetered_fuel_spend=0,
    scheme_eligible=False,
)

# %%
dummy_household.get_tidy_summary()

# %%
summary = pd.concat(
    [dummy_household.get_tidy_summary(), eligible_1.get_tidy_summary()],
)
summary

# %%
