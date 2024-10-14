import streamlit as st
import pandas as pd
import altair as alt
import tempfile

from getters.load_data import (
    download_annex_4,
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
    ofgem_archetypes_data,
)

from levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from summary import process_rebalancing_scenarios

st.title("Policy cost levies rebalancing model V1")

# Download Annex 4 data
st.subheader("**Downloading latest Ofgem policy cost data 🗃️**", divider=True)

with tempfile.TemporaryDirectory() as tmpdir:
    url = "https://www.ofgem.gov.uk/sites/default/files/2024-08/Annex_4_-_Policy_cost_allowance_methodology_v1.19 (1).xlsx"
    with st.spinner("Downloading latest Ofgem policy cost data..."):
        download_annex_4(url, tmpdir)
    st.success("Latest policy cost data downloaded!")

    # Load energy consumption profiles
    ofgem_archetypes_df = ofgem_archetypes_data()

    # Initialise existing levies
    levies = [
        RO.from_dataframe(
            process_data_RO(tmpdir), denominator=94_200_366
        ),  # domestic denominator
        AAHEDC.from_dataframe(
            process_data_AAHEDC(tmpdir), denominator=94_200_366
        ),  # domestic denominator
        GGL.from_dataframe(
            process_data_GGL(tmpdir), denominator=24_503_683
        ),  # domestic denominator
        WHD.from_dataframe(process_data_WHD(tmpdir)),  # domestic only levy
        ECO.from_dataframe(process_data_ECO(tmpdir)),  # domestic only levy
        FIT.from_dataframe(
            process_data_FIT(tmpdir),
            revenue=689_233_317,  # This revenue is the domestic share based on domestic electricity supply/total elligible supply.
        ),
    ]


# Take rebalancing scenario name
st.subheader("**What would you like to call your rebalancing scenario?**", divider=True)
scenario_name = st.text_input("Enter scenario name")
if not scenario_name:
    st.error("Please provide a scenario name.")

# Take user input for choice of denominator data for rebalancing
st.subheader("**Set charging base**", divider=True)
denominator_data_status = st.radio(
    "For rebalancing, use denominator data: ",
    ("Subnational accounts, domestic", "Custom"),
)
if denominator_data_status == "Subnational accounts, domestic":
    supply_elec = 94_200_366
    supply_gas = 265_197_947
    customers_gas = 24_503_683
    customers_elec = 29_078_770
else:
    supply_elec = st.number_input("Electricity supply denominator (MWh)")
    supply_gas = st.number_input("Gas supply denominator (MWh)")
    customers_elec = st.number_input("Number of electricity customers")
    customers_gas = st.number_input("Number of gas customers")

denominator_values = {
    "supply_elec": supply_elec,
    "supply_gas": supply_gas,
    "customers_gas": customers_gas,
    "customers_elec": customers_elec,
}
denominators = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}


# Take rebalancing weights for electricity/gas/tax
st.subheader(
    "**What percentage of each levy revenue should be reapportioned to :blue[electricity], :red[gas] and :violet[general taxation]?**",
    divider=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**:blue[Electricity]**")
    new_electricity_weights = {}
    for levy in levies:
        new_electricity_weights[levy.short_name] = st.number_input(
            f"{levy.name} electricity weight (%): ", 0, 100
        )
with col2:
    st.markdown("**:red[Gas]**")
    new_gas_weights = {}
    for levy in levies:
        new_gas_weights[levy.short_name] = st.number_input(
            f"{levy.name} gas weight (%): ", 0, 100
        )
with col3:
    st.markdown("**:violet[General taxation]**")
    new_tax_weights = {}
    for levy in levies:
        new_tax_weights[levy.short_name] = st.number_input(
            f"{levy.name} tax weight (%): ", 0, 100
        )

# Summation check
for levy in levies:
    if (
        new_electricity_weights.get(levy.short_name)
        + new_gas_weights.get(levy.short_name)
        + new_tax_weights.get(levy.short_name)
        != 100
    ):
        st.error(f"Please ensure percentage weights add up to 100 for {levy.name}.")

# Take rebalancing weights for fixed/variable
st.subheader(
    "**What percentage of each levy revenue should be raised from fixed vs. variable charges?**",
    divider=True,
)
new_fixed_electricity_weights = {}
new_variable_electricity_weights = {}
new_fixed_gas_weights = {}
new_variable_gas_weights = {}

col1, col2 = st.columns(2)

with col1:
    if sum([new_electricity_weights.get(levy.short_name) for levy in levies]) == 0:
        st.markdown("**No revenue to be raised through :blue[electricity].**")
    else:
        st.markdown(
            f"**What percentage of each levy revenue from :blue[electricity] should be from fixed vs. variable charges?**"
        )

    for levy in levies:
        if new_electricity_weights.get(levy.short_name) > 0:
            st.markdown(f"**{levy.name}**")
            new_fixed_electricity_weights[levy.short_name] = st.slider(
                f"Electricity, fixed weight ({levy.short_name.upper()}) (%)"
            )
            new_variable_electricity_weights[levy.short_name] = (
                100 - new_fixed_electricity_weights[levy.short_name]
            )
            st.write(
                f"Electricity, variable weight ({levy.short_name.upper()}): {new_variable_electricity_weights.get(levy.short_name)} %"
            )
        else:
            new_fixed_electricity_weights[levy.short_name] = 0
            new_variable_electricity_weights[levy.short_name] = 0

with col2:
    if sum([new_gas_weights.get(levy.short_name) for levy in levies]) == 0:
        st.markdown("**No revenue to be raised through :red[gas].**")
    else:
        st.markdown(
            f"**What percentage of each levy revenue from :red[gas] should be from fixed vs. variable charges?**"
        )

    for levy in levies:

        if new_gas_weights.get(levy.short_name) > 0:
            st.markdown(f"**{levy.name}**")
            new_fixed_gas_weights[levy.short_name] = st.slider(
                f"Gas, fixed weight ({levy.short_name.upper()}) (%)"
            )
            new_variable_gas_weights[levy.short_name] = (
                100 - new_fixed_gas_weights[levy.short_name]
            )
            st.write(
                f"Gas, variable weight ({levy.short_name.upper()}): {new_variable_gas_weights.get(levy.short_name)} %"
            )

        else:
            new_fixed_gas_weights[levy.short_name] = 0
            new_variable_gas_weights[levy.short_name] = 0

weights = {
    scenario_name: {
        levy.short_name: {
            "new_electricity_weight": new_electricity_weights.get(levy.short_name)
            / 100,
            "new_gas_weight": new_gas_weights.get(levy.short_name) / 100,
            "new_tax_weight": new_tax_weights.get(levy.short_name) / 100,
            "new_variable_weight_elec": new_variable_electricity_weights.get(
                levy.short_name
            )
            / 100,
            "new_fixed_weight_elec": new_fixed_electricity_weights.get(levy.short_name)
            / 100,
            "new_variable_weight_gas": new_variable_gas_weights.get(levy.short_name)
            / 100,
            "new_fixed_weight_gas": new_fixed_gas_weights.get(levy.short_name) / 100,
        }
        for levy in levies
    }
}

# Produce scenario results
st.subheader("**Is scenario all set?**")

if st.button("Generate my scenario! 🤖"):
    # Generate full output dataframe
    scenario_outputs = process_rebalancing_scenarios(
        levies,
        weights,  # implemented as user input
        denominators,  # potential user input
        ofgem_archetypes_df,
        "AnnualConsumptionProfile",
        "ElectricitySingleRatekWh",
        "GaskWh",
        ["fixed", "variable", "total"],
        1_000,
    )

    st.subheader("**Summary**", divider=True)

    st.markdown(
        "**Amount not levied on energy (e.g. to be raised via general taxation)**"
    )
    for levy in levies:
        st.markdown(
            f"{levy.name}: £{((new_tax_weights.get(levy.short_name)/100)*levy.revenue)/1_000_000_000} billion."
        )

    # Summary pivot table
    summary_data = scenario_outputs.pivot_table(
        index=[
            "AnnualConsumptionProfile",
            "scenario",
        ],
        columns="variable",
        values="value",
        aggfunc="sum",
    ).reset_index()
    st.markdown(
        "*Hover over the table below to download using the 'Download as CSV' button.*"
    )
    st.write(summary_data)

    # Summary figure - Dot plot
    baseline_totals = scenario_outputs.loc[
        (scenario_outputs["scenario"] == "Baseline")
        & (scenario_outputs["variable"] == "total levy costs")
    ]
    scenario_totals = scenario_outputs.loc[
        (scenario_outputs["scenario"] == scenario_name)
        & (scenario_outputs["variable"] == "total levy costs")
    ]
    cost_changes = (
        scenario_totals.value.reset_index(drop=True)
        - baseline_totals.value.reset_index(drop=True)
    ).rename("Policy cost change")

    chart_data = pd.concat(
        [
            ofgem_archetypes_df["AnnualConsumptionProfile"].rename(
                "Energy consumer archetype"
            ),
            cost_changes,
            ofgem_archetypes_df["GrossAnnualHouseholdIncome"],
            ofgem_archetypes_df["ArchetypeNickname"],
            ofgem_archetypes_df["ArchetypeSize"],
            ofgem_archetypes_df["ArchetypeHeatingFuel"],
        ],
        axis=1,
    )

    chart_data = chart_data.sort_values(
        "GrossAnnualHouseholdIncome", ascending=True
    ).reset_index(drop=True)

    chart = alt.Chart(chart_data)
    points = chart.mark_point(opacity=1, filled=True).encode(
        x=alt.X(
            "Policy cost change:Q",
            axis=alt.Axis(grid=True),
            title="Total policy cost change from status quo(£)",
        ),
        y=alt.Y(
            "ArchetypeNickname:N",
            axis=alt.Axis(grid=True, labelLimit=500),
            sort=None,
            title="Energy consumer archetype (low to high income)",
        ),
        size="ArchetypeSize:Q",
        color="ArchetypeHeatingFuel:N",
    )
    rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
    chart = (points + rule).properties(width=1200)
    chart = chart.configure_axisY(
        titleAngle=0,
        titleAlign="left",
        titleY=-10,
        titleX=-300,
    )

    st.altair_chart(chart)
