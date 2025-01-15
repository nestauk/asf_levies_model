# %%
from asf_levies_model.levies import RO, AAHEDC, GGL, ECO, WHD, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.consumers import Consumer

from asf_levies_model.getters.load_data import (
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_ECO,
    process_data_WHD,
    process_data_FIT,
    process_tariff_elec_other_payment_nil,
    process_tariff_elec_other_payment_typical,
    process_tariff_gas_other_payment_nil,
    process_tariff_gas_other_payment_typical,
)

from asf_levies_model.getters.load_data import ofgem_archetypes_data

# %%
# Some required data
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
levies = [
    RO.from_dataframe(process_data_RO(), denominator=supply_elec),
    AAHEDC.from_dataframe(process_data_AAHEDC(), denominator=supply_elec),
    GGL.from_dataframe(process_data_GGL(), denominator=customers_gas),
    WHD.from_dataframe(
        process_data_WHD(), customers_gas=customers_gas, customers_elec=customers_elec
    ),
    ECO.from_dataframe(process_data_ECO()),
    FIT.from_dataframe(
        process_data_FIT(),
        scaling_factor=fit_scaling_factor,
    ),
]

# %%
# Initialise tariffs (Other Payment method)
elec_other_payment_nil = process_tariff_elec_other_payment_nil()
elec_other_payment_typical = process_tariff_elec_other_payment_typical()
gas_other_payment_nil = process_tariff_gas_other_payment_nil()
gas_other_payment_typical = process_tariff_gas_other_payment_typical()

# %%
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

# %%
# rebalance baseline levies
print(sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies]))
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]
print(sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies]))

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
# ### Consumers
# #### Flat Rebates
# A given consumer has a subtotal gas and electricity bill cost, which reflects the energy tariff including any actions on levies (rebalancing and/or removal to taxation).
#
# Consumer can then be acted upon in terms of social support adjustments.
#
# The simplest is a flat adjustment in which a fixed amount can be subtracted (or added) to a bill to generate a final bill after support.
#
# The total cost of a flat rebate is: rebate amount $\times$ eligible consumers.

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

# %%
# Check the subtotal bill for a typical consumer (this is the bill before support)
typical.electricity_subtotal_bill, typical.gas_subtotal_bill

# %%
# Evaluate a flat support rate of £150 to electricity bills
if typical.scheme_eligible:
    typical = typical.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=-150,
        adjustment_mode="flat adjustment",
    )
# Get final bill
# In this case there is no adjustment to the final bill as the consumer is not scheme eligible.
typical.electricity_bill, typical.gas_bill

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
# Get final bill
# In this case there is an adjustment to the electricity bill.
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %% [markdown]
# #### Percentage Rebates
#
# An alternative to a flat rebate is a percentage rebate.
#
# The total cost is the absolute value of the discount $\times$ eligible consumers.
#
# This might require a calculation based on archetypes and/or distributions.

# %%
# Evaluate a percentage discount support rate of 15% to electricity bills
if typical_eligible.scheme_eligible:
    typical_eligible = typical_eligible.apply_social_support_adjustment(
        adjustment_fuel="electricity",
        adjustment_parameter=15,
        adjustment_mode="percentage discount",
    )
# Get final bill
# In this case there is an adjustment to the electricity bill.
typical_eligible.electricity_bill, typical_eligible.gas_bill

# %% [markdown]
# #### Unit adjustments
#
# Unit adjustments provide a rebate against consumption.
#
# Here the adjustment parameter is in £/MWh. So a value of 1 gives a discount of £1 for each MWh consumed, or approximately £2.70 discount for a typical household.
#
# This means that an adjustment parameter of £1000 is effectively £1 per kWh. A typical discount will likely lie between 1 and 100.

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

# %% [markdown]
# #### Stacking Adjustments
#
# There may be a case for stacking support of the same or different type, however it's not currently possible to do that. We should explore how best to achieve it if it is of interest.
