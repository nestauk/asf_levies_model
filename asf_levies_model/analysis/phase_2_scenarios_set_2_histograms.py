import pandas as pd
import numpy as np
from datetime import datetime
from asf_levies_model import PROJECT_DIR
import altair as alt

"""
Load summary table
"""

# Results with mean consumption
today = datetime.now()
date_str = today.strftime("%Y%m%d")
pickle_path_summary = (
    f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_summary_table.pkl"
)
master_summary = pd.read_pickle(pickle_path_summary)

# Results with 95th percentile consumption
today = datetime.now()
date_str = today.strftime("%Y%m%d")
pickle_path_summary = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct_summary_table.pkl"
master_summary_95pct = pd.read_pickle(pickle_path_summary)

"""
Functions to make histogram and dataframe for making histogram in Flourish
"""


def create_weighted_histogram(
    df: pd.DataFrame,
    scenario_support_name: str,
    eligible_only: bool = True,
    x_limits=(-750, 250),
    num_bins=20,
    y_limits=(0, 20_000_000),
):
    if eligible_only:
        df = df[
            (df["ScenarioSupport"] == scenario_support_name)
            & (df["EligibleForSupport"] == True)
        ]
    else:
        df = df[df["ScenarioSupport"] == scenario_support_name]

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            alt.X(
                "Net change in annual energy bill:Q",
                bin=alt.Bin(extent=x_limits, maxbins=num_bins),
                title="Net Change in Annual Energy Bill",
                scale=alt.Scale(domain=x_limits),
            ),
            alt.Y(
                "sum(GroupSize):Q",
                title="Number of households",
                scale=alt.Scale(domain=y_limits),
            ),
            alt.Color(
                "main_heating_fuel:N",
                scale=alt.Scale(
                    domain=["Gas", "Electricity", "Electricity/Other", "Other"],
                    range=["blue", "green", "grey", "pink"],
                ),
            ),
            tooltip=[
                "main_heating_fuel:N",
                "sum(GroupSize):Q",
            ],
        )
        .properties(title=f"{scenario_support_name}, Eligible only: {eligible_only}")
    )

    return chart


def create_weighted_histogram_dataframe(
    df: pd.DataFrame,
    scenario_support_name: str,
    eligible_only: bool = True,
):
    # Define custom bins from -750 to 250 with intervals of 50
    bins = np.arange(-750, 251, 50)
    bin_labels = pd.IntervalIndex.from_breaks(bins, closed="left")

    if eligible_only:
        df = df.loc[
            (df["ScenarioSupport"] == scenario_support_name)
            & (df["EligibleForSupport"] == True)
        ].copy()
    else:
        df = df.loc[df["ScenarioSupport"] == scenario_support_name].copy()

    # Bin data using defined bins
    df.loc[:, "binned"] = pd.cut(
        df["Net change in annual energy bill"], bins=bin_labels
    )

    # Aggregate by bin and heating fuel type
    grouped_df = (
        df.groupby(["binned", "main_heating_fuel"], observed=True)
        .agg({"GroupSize": "sum"})
        .reset_index()
    )

    # Pivot and reindex
    pivot_df = grouped_df.pivot(
        index="binned", columns="main_heating_fuel", values="GroupSize"
    ).reindex(bin_labels, fill_value=np.nan)

    # Ensure all heating fuel columns are present
    all_fuel_types = df["main_heating_fuel"].unique()
    pivot_df = pivot_df.reindex(columns=all_fuel_types, fill_value=np.nan)

    # Rename the index to include the scenario support name
    pivot_df = pivot_df.rename_axis(index=scenario_support_name)

    return pivot_df[["Gas", "Electricity", "Electricity/Other", "Other"]]


"""
Create dataframes for all scenarios
"""

# Mean consumption
scenario_names = master_summary["ScenarioSupport"].unique().tolist()
scenario_histogram_tables = {}
for scenario in scenario_names:
    scenario_histogram_tables[scenario] = create_weighted_histogram_dataframe(
        df=master_summary, scenario_support_name=scenario, eligible_only=False
    )

# 95pct consumption
scenario_histogram_tables_95pct = {}
for scenario in scenario_names:
    scenario_histogram_tables_95pct[scenario] = create_weighted_histogram_dataframe(
        df=master_summary_95pct, scenario_support_name=scenario, eligible_only=False
    )

"""
Saving Flourish data tables to Excel
"""

histograms_filename = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_histogram_tables.xlsx"
try:
    with pd.ExcelWriter(histograms_filename, engine="xlsxwriter") as writer:
        # Individual scenario tables
        i = 1
        for scenario in scenario_names:
            scenario_histogram_tables[scenario].to_excel(
                writer, sheet_name=f"Histogram_scenario_{i}", index=True
            )
            i = i + 1
    print("Histogram tables for Flourish successfully written to Excel file.")
except Exception as e:
    print(f"Failed to write Excel file: {e}")

histograms_filename_95pct = f"{PROJECT_DIR}/outputs/data/{date_str}_phase_2_scenarios_set_2_95pct_histogram_tables.xlsx"
try:
    with pd.ExcelWriter(histograms_filename_95pct, engine="xlsxwriter") as writer:
        # Individual scenario tables
        i = 1
        for scenario in scenario_names:
            scenario_histogram_tables_95pct[scenario].to_excel(
                writer, sheet_name=f"Histogram_scenario_{i}", index=True
            )
            i = i + 1
    print(
        "Histogram tables (95th percentile) for Flourish successfully written to Excel file."
    )
except Exception as e:
    print(f"Failed to write Excel file: {e}")
