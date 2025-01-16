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
import numpy as np
from scipy.stats import norm
from scipy.stats import lognorm
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

from asf_levies_model.getters.load_data import ofgem_archetypes_data

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
# Fitting distributions to archetype consumption


# %% [markdown]
# Normal distribution


# %%
def archetype_normal_fit(df: pd.DataFrame, archetype: str, fuel: str):

    # Normal distribution
    fit_params_ppf, _fit_covariances = curve_fit(
        lambda x, mu, sigma: norm(mu, sigma).ppf(x),
        xdata=df["Percentile"][1:6],
        ydata=df[archetype][1:6],
    )

    # Extract fitted parameters
    mu, sigma = fit_params_ppf

    # Generate the fitted curve
    x_fit = np.linspace(0.01, 0.99, 100)  # Percentiles
    fit = norm(mu, sigma).ppf(x_fit)

    # Plotting
    f, ax = plt.subplots()

    # Original data
    ax.plot(
        electricity_profiles["Percentile"],
        electricity_profiles["A1"],
        marker="o",
        label="Original Data",
    )

    # Fitted curve
    ax.plot(
        x_fit,
        fit,
        label=f"Fitted PPF (mu={mu:.2f}, sigma={sigma:.2f})",
    )

    # Customize plot
    ax.set_ylabel(f"{fuel} consumption (kWh/year)")
    ax.set_xlabel("Percentile")
    plt.grid()
    ax.legend()


# %%
archetype_normal_fit(electricity_profiles, "A1", "electricity")


# %%
def archetype_lognormal_fit(df: pd.DataFrame, archetype: str, fuel: str):

    # Lognormal distribution: curve fit for percentiles
    fit_params_ppf, _fit_covariances = curve_fit(
        lambda x, s, loc, scale: lognorm(s, loc, scale).ppf(x),
        xdata=df["Percentile"][1:6],
        ydata=df[archetype][1:6],
        p0=[1, 0, df[archetype][1:6].mean()],  # Initial guess for [s, loc, scale]
    )

    # Extract fitted parameters
    s, loc, scale = fit_params_ppf

    # Generate the fitted curve
    x_fit = np.linspace(0.01, 0.99, 100)  # Percentiles
    fit = lognorm(s, loc, scale).ppf(x_fit)

    # Plotting
    f, ax = plt.subplots()

    # Original data
    ax.plot(
        electricity_profiles["Percentile"],
        electricity_profiles["A1"],
        marker="o",
        label="Original Data",
    )

    # Fitted curve
    ax.plot(
        x_fit,
        fit,
        label=f"Fitted Lognormal (s={s:.2f}, loc={loc:.2f}, scale={scale:.2f})",
    )

    # Customize plot
    ax.set_ylabel(f"{fuel} consumption (kWh/year)")
    ax.set_xlabel("Percentile")
    plt.grid()
    ax.legend()


# %%
archetype_lognormal_fit(electricity_profiles, "A1", "electricity")

# %%

# %%
