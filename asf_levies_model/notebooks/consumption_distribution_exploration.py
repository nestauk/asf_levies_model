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

from asf_levies_model.getters.load_data import ofgem_archetypes_data
import matplotlib.pyplot as plt

# %% [markdown]
# Load consumption data and transform

# %%
ofgem_archetypes_df = ofgem_archetypes_data()

# %%
gas = ofgem_archetypes_df[["AnnualConsumptionProfile", "GaskWh"]].copy(deep=True)

gas = gas[gas["AnnualConsumptionProfile"] != "Typical"]

suffix = ["_Min", "_5PCT", "_25PCT", "_50PCT", "_75PCT", "_95PCT", "_Max"]

gas["Percentile"] = ""

for s in suffix:
    gas["Percentile"] = gas.apply(
        lambda row: (
            s.strip("_") if s in row["AnnualConsumptionProfile"] else row["Percentile"]
        ),
        axis=1,
    )
    gas["AnnualConsumptionProfile"] = gas["AnnualConsumptionProfile"].str.replace(
        s, "", regex=False
    )

gas = gas[gas["Percentile"] != ""]

gas["Percentile"] = gas["Percentile"].str.replace("PCT", "", regex=False)

gas["Percentile"] = gas["Percentile"].str.replace("Min", "0", regex=False)

gas["Percentile"] = gas["Percentile"].str.replace("Max", "100", regex=False)

# %%
gas_profiles = gas.pivot_table(
    values="GaskWh",
    index="Percentile",
    columns="AnnualConsumptionProfile",
).reset_index()
gas_profiles = gas_profiles.astype("float64")

# Reorder
gas_profiles = gas_profiles.sort_values(by=["Percentile"]).reset_index(drop=True)

# %%
electricity = ofgem_archetypes_df[
    ["AnnualConsumptionProfile", "ElectricitySingleRatekWh"]
].copy(deep=True)

electricity = electricity[electricity["AnnualConsumptionProfile"] != "Typical"]

suffix = ["_Min", "_5PCT", "_25PCT", "_50PCT", "_75PCT", "_95PCT", "_Max"]

electricity["Percentile"] = ""

for s in suffix:
    electricity["Percentile"] = electricity.apply(
        lambda row: (
            s.strip("_") if s in row["AnnualConsumptionProfile"] else row["Percentile"]
        ),
        axis=1,
    )
    electricity["AnnualConsumptionProfile"] = electricity[
        "AnnualConsumptionProfile"
    ].str.replace(s, "", regex=False)

electricity = electricity[electricity["Percentile"] != ""]

electricity["Percentile"] = electricity["Percentile"].str.replace(
    "PCT", "", regex=False
)

electricity["Percentile"] = electricity["Percentile"].str.replace(
    "Min", "0", regex=False
)

electricity["Percentile"] = electricity["Percentile"].str.replace(
    "Max", "100", regex=False
)

# %%
electricity_profiles = electricity.pivot_table(
    values="ElectricitySingleRatekWh",
    index="Percentile",
    columns="AnnualConsumptionProfile",
).reset_index()
electricity_profiles = electricity_profiles.astype("float64")

# Reorder
electricity_profiles = electricity_profiles.sort_values(by=["Percentile"]).reset_index(
    drop=True
)

electricity_profiles["Percentile"] = electricity_profiles["Percentile"] / 100


# %% [markdown]
# Exploring archetypes


# %%
def electricity_cdf(df: pd.DataFrame, archetype: str):
    x = df[archetype][1:7]
    y = df["Percentile"][1:7]

    fig = plt.plot(
        x,
        y,
        marker="o",
        label=archetype,
    )

    plt.ylabel("Proportion")
    plt.xlabel("Electricity consumption (kWh/year)")
    plt.yticks(y)
    plt.legend()
    plt.grid()

    return fig


# %%
def gas_cdf(df: pd.DataFrame, archetype: str):
    x = df[archetype][1:7]
    y = df["Percentile"][1:7]

    fig = plt.plot(
        x,
        y,
        marker="o",
        label=archetype,
    )

    plt.ylabel("Proportion")
    plt.xlabel("Gas consumption (kWh/year)")
    plt.yticks(y)
    plt.legend()
    plt.grid()

    return fig


# %%
electricity_cdf(electricity_profiles, "A1")

# %%
gas_cdf(gas_profiles, "A1")

# %%
