# %% [markdown]
#  Setting up status quo levies and tariffs.

# %%
from asf_levies_model.getters.load_data import (
    download_annex_4,
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, ECO4, GBIS, FIT


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

denominators_standard = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}

denominators_split = {
    key: denominator_values
    for key in ["ro", "aahedc", "ggl", "whd", "eco4", "gbis", "fit"]
}

# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# Annex 4 and initialise levies
fileobject = download_annex_4(as_fileobject=True)
standard_levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=24_503_683),
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

split_levies = [
    RO.from_dataframe(process_data_RO(fileobject), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(fileobject), denominator=24_503_683),
    WHD.from_dataframe(
        process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
    ),
    ECO4.from_dataframe(process_data_ECO(fileobject)),
    GBIS.from_dataframe(process_data_ECO(fileobject)),
    FIT.from_dataframe(
        process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
]

fileobject.close()

# %%
# Status quo - Rebalance baseline to reflect denominators
status_quo_standard = {}  # Recreating status quo
for levy in standard_levies:
    status_quo_standard[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

status_quo_split = {}  # Recreating status quo
for levy in split_levies:
    status_quo_split[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

# rebalance baseline levies
standard_levies = [
    levy.rebalance_levy(
        **status_quo_standard.get(levy.short_name),
        **denominators_standard.get(levy.short_name),
    )
    for levy in standard_levies
]

split_levies = [
    levy.rebalance_levy(
        **status_quo_split.get(levy.short_name),
        **denominators_split.get(levy.short_name),
    )
    for levy in split_levies
]

# %%
assert sum(
    [levy.calculate_levy(2.7, 11.5, True, True) for levy in standard_levies]
) == sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in split_levies])
