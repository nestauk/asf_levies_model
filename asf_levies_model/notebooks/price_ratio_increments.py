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

from asf_levies_model.levies import Levy, RO, AAHEDC, GGL, WHD, ECO, FIT

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
# Create meta levy of all levies charged on electricity or gas units
AllVar = Levy
AllVar.name = "All levies"

# Add revenue of levies that are on variable charges
# RO, AAHEDC, ECO, FIT
ro = levies[0]
aahedc = levies[1]
eco = levies[4]
fit = levies[5]
AllVar.revenue = ro.revenue + aahedc.revenue + eco.revenue + fit.revenue

AllVar.electricity_weight = 1
AllVar.gas_weight = 0
AllVar.tax_weight = 0

AllVar.electricity_variable_weight = 1
AllVar.electricity_fixed_weight = 0

AllVar.gas_variable_weight = 1
AllVar.gas_fixed_weight = 1

AllVar.electricity_variable_rate = AllVar.revenue / supply_elec
AllVar.electricity_fixed_rate = 0
AllVar.gas_variable_rate = 0
AllVar.gas_fixed_rate = 0

AllVar.general_taxation = 0

# %%
# Annex 9 and initialise tariffs (Other Payment method)
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
# Create bill objects
elec_bill = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)
gas_bill = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# %%
gas_weights = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]

ratios = []
for weight in gas_weights:

    rebalanced_levy = AllVar.rebalance_levy(
        AllVar,
        new_electricity_weight=1 - weight,
        new_gas_weight=weight,
        new_tax_weight=0,
        new_variable_weight_elec=1,
        new_fixed_weight_elec=0,
        new_variable_weight_gas=1,
        new_fixed_weight_gas=0,
        supply_gas=supply_gas,
        supply_elec=supply_elec,
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        inplace=False,
    )

    elec_bill.pc_nil = rebalanced_levy.calculate_fixed_levy(
        rebalanced_levy, electricity_customer=True, gas_customer=False
    )
    elec_bill.pc = rebalanced_levy.calculate_variable_levy(rebalanced_levy, 1, 0)

    gas_bill.pc_nil = rebalanced_levy.calculate_fixed_levy(
        rebalanced_levy, electricity_customer=False, gas_customer=True
    )
    gas_bill.pc = rebalanced_levy.calculate_variable_levy(rebalanced_levy, 0, 1)

    ratios.append(
        elec_bill.calculate_variable_consumption(1)
        / gas_bill.calculate_variable_consumption(1)
    )

# %%
pd.DataFrame(
    {
        "Gas proportion of revenue from levies charged on units": gas_weights,
        "Electricity to gas unit cost ratio": ratios,
    }
)

# %%
superimposed_gas_weights = [
    (eco.revenue * eco.gas_weight) / AllVar.revenue,
    ((eco.revenue * eco.gas_weight) + fit.revenue) / AllVar.revenue,
    ((eco.revenue * eco.gas_weight) + ro.revenue) / AllVar.revenue,
    ((eco.revenue * eco.gas_weight) + fit.revenue + ro.revenue) / AllVar.revenue,
    # ((eco.revenue * eco.gas_weight) + fit.revenue + ro.revenue + aahedc.revenue)/ AllVar.revenue,
]

superimposed_ratios = []
for weight in superimposed_gas_weights:

    rebalanced_levy = AllVar.rebalance_levy(
        AllVar,
        new_electricity_weight=1 - weight,
        new_gas_weight=weight,
        new_tax_weight=0,
        new_variable_weight_elec=1,
        new_fixed_weight_elec=0,
        new_variable_weight_gas=1,
        new_fixed_weight_gas=0,
        supply_gas=supply_gas,
        supply_elec=supply_elec,
        customers_gas=customers_gas,
        customers_elec=customers_elec,
        inplace=False,
    )

    elec_bill.pc_nil = rebalanced_levy.calculate_fixed_levy(
        rebalanced_levy, electricity_customer=True, gas_customer=False
    )
    elec_bill.pc = rebalanced_levy.calculate_variable_levy(rebalanced_levy, 1, 0)

    gas_bill.pc_nil = rebalanced_levy.calculate_fixed_levy(
        rebalanced_levy, electricity_customer=False, gas_customer=True
    )
    gas_bill.pc = rebalanced_levy.calculate_variable_levy(rebalanced_levy, 0, 1)

    superimposed_ratios.append(
        elec_bill.calculate_variable_consumption(1)
        / gas_bill.calculate_variable_consumption(1)
    )

# %%
pd.DataFrame(
    {
        "Gas proportion of revenue from levies charged on units": superimposed_gas_weights,
        "Electricity to gas unit cost ratio": superimposed_ratios,
    }
)

# %%
import matplotlib.pyplot as plt

# Incremental profile
plt.scatter(gas_weights, ratios)

# Super imposed points to highlight
# Status quo, FIT removed, RO removed, FIT and RO removed
plt.scatter(superimposed_gas_weights, superimposed_ratios)

plt.xlabel("Gas proportion of revenue from levies charged on units")
plt.ylabel("Electricity to gas unit cost ratio")
plt.title("Only rebalancing levies on variable charges")
plt.grid(True)
for i in range(len(gas_weights)):
    plt.text(gas_weights[i], ratios[i], f"({gas_weights[i]:.2f}, {ratios[i]:.2f})")
for i in range(len(superimposed_gas_weights)):
    plt.text(
        superimposed_gas_weights[i],
        superimposed_ratios[i],
        f"({superimposed_gas_weights[i]:.2f}, {superimposed_ratios[i]:.2f})",
    )

# Add trendline
import numpy as np
from scipy.optimize import curve_fit


# Exponential function to fit
def exp_func(x, a, b, c):
    return a * np.exp(b * x) + c


# Fit the data to the exponential model
params1, _ = curve_fit(exp_func, gas_weights, ratios)
# Plot trendline
x1_smooth = np.linspace(min(gas_weights), max(gas_weights), 100)
plt.plot(
    x1_smooth,
    exp_func(x1_smooth, *params1),
    label="Exp. Trendline 1",
    color="blue",
    linestyle="--",
)

# %%
