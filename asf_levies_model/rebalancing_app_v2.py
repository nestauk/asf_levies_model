"""
Levies rebalancing app.
"""

import streamlit as st
import pandas as pd
import altair as alt

from getters.load_data import (
    download_annex_4,
    download_annex_9,
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
    ofgem_archetypes_data,
    process_tariff_elec_other_payment_nil,
    process_tariff_elec_other_payment_typical,
    process_tariff_gas_other_payment_nil,
    process_tariff_gas_other_payment_typical,
    process_tariff_elec_ppm_nil,
    process_tariff_elec_ppm_typical,
    process_tariff_gas_ppm_nil,
    process_tariff_gas_ppm_typical,
    process_tariff_elec_standard_credit_nil,
    process_tariff_elec_standard_credit_typical,
    process_tariff_gas_standard_credit_nil,
    process_tariff_gas_standard_credit_typical,
)

from levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from summary import (
    process_rebalancing_scenarios,
    process_rebalancing_scenario_bills,
)

from utils.st_components import get_preset_weights, get_bills

# Set page title and configuration
st.set_page_config(
    page_title="Nesta Levies Rebalancing Model",
    layout="wide",
    # page_icon="INSERT_ICON_URL_HERE"
)

# Set denominator values as domestic values from subnational consumption accounts dataset (GB)
denominator_values = {
    "supply_elec": 94_200_366,
    "supply_gas": 265_197_947,
    "customers_gas": 24_503_683,
    "customers_elec": 29_078_770,
}
denominators = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}


# Load Ofgem energy consumer archetypes data
@st.cache_data
def load_archetypes():
    return ofgem_archetypes_data()


ofgem_archetypes_df = load_archetypes()


# Load Annex 4 data
@st.cache_data
def load_annex_4():
    return download_annex_4(as_fileobject=True)


fileobject_annex_4 = load_annex_4()

# Instantiate baseline levies
levies = [
    RO.from_dataframe(process_data_RO(fileobject_annex_4), denominator=94_200_366),
    AAHEDC.from_dataframe(
        process_data_AAHEDC(fileobject_annex_4), denominator=94_200_366
    ),
    GGL.from_dataframe(process_data_GGL(fileobject_annex_4), denominator=24_503_683),
    WHD.from_dataframe(process_data_WHD(fileobject_annex_4)),
    ECO.from_dataframe(process_data_ECO(fileobject_annex_4)),
    FIT.from_dataframe(process_data_FIT(fileobject_annex_4), revenue=689_233_317),
]
fileobject_annex_4.close()

### TO REFACTOR
# Re-balance baseline levies to reflect denominator choices
# We can't meaningfully replicate ofgem's levy denominators exactly, so we'll first rebalance
# the levy baseline so that comparisons are internally consistent.
# This will lead to different bill amounts to those published by Ofgem.

status_quo = {}
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

# Manually update WHD weights according to denominator balance
status_quo["whd"]["new_electricity_weight"] = round(
    denominators["whd"]["customers_elec"]
    / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]),
    2,
)
status_quo["whd"]["new_gas_weight"] = round(
    denominators["whd"]["customers_gas"]
    / (denominators["whd"]["customers_elec"] + denominators["whd"]["customers_gas"]),
    2,
)

# Rebalance baseline levies
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]


# Load Annex 9 data
@st.cache_data
def load_annex_9():
    return download_annex_9(as_fileobject=True)


fileobject_annex_9 = load_annex_9()

### TO REFACTOR
# Load tariff tables from Annex 9
# Other payment
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject_annex_9)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(
    fileobject_annex_9
)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject_annex_9)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject_annex_9)
# Prepayment meter
elec_ppm_nil = process_tariff_elec_ppm_nil(fileobject_annex_9)
elec_ppm_typical = process_tariff_elec_ppm_typical(fileobject_annex_9)
gas_ppm_nil = process_tariff_gas_ppm_nil(fileobject_annex_9)
gas_ppm_typical = process_tariff_gas_ppm_typical(fileobject_annex_9)
# Standard Credit
elec_standard_credit_nil = process_tariff_elec_standard_credit_nil(fileobject_annex_9)
elec_standard_credit_typical = process_tariff_elec_standard_credit_typical(
    fileobject_annex_9
)
gas_standard_credit_nil = process_tariff_gas_standard_credit_nil(fileobject_annex_9)
gas_standard_credit_typical = process_tariff_gas_standard_credit_typical(
    fileobject_annex_9
)
fileobject_annex_9.close()

# Create dictionaries for tariff data
elec_tariff_data = {
    "other_payment": (elec_other_payment_nil, elec_other_payment_typical),
    "ppm": (elec_ppm_nil, elec_ppm_typical),
    "standard_credit": (elec_standard_credit_nil, elec_standard_credit_typical),
}

gas_tariff_data = {
    "other_payment": (gas_other_payment_nil, gas_other_payment_typical),
    "ppm": (gas_ppm_nil, gas_ppm_typical),
    "standard_credit": (gas_standard_credit_nil, gas_standard_credit_typical),
}

# Lay out header section
row1_1, row1_2 = st.columns((2, 3))
with row1_1:
    st.title("Nesta Green Levies Rebalancing Model")  ### TO DO: Workshop title

with row1_2:
    st.markdown("######")
    st.markdown(
        "**What is this tool?** As part of Nesta's project on [making energy cheaper by rebalancing levies](https://www.nesta.org.uk/project/finding-ways-to-deliver-cheaper-electricity-by-rebalancing-levies/), this tool allows you to model different approaches to rebalancing policy costs between electricity and gas levies, or removing them off bills to general taxation."
    )
st.markdown(
    "Results below show the effects of your rebalancing approach on the [**electricity to gas unit cost ratio**](https://www.nesta.org.uk/blog/the-electricity-to-gas-price-ratio-explained-how-a-green-ratio-would-make-bills-cheaper-and-greener/) and the energy bills of different [**UK energy consumer archetypes**](https://www.ofgem.gov.uk/sites/default/files/2024-02/Ofgem_archetypes_update_2024_FinalReport_v4.1.3.pdf)."
)

scenario_name = "Rebalanced"

# Instantiate a state key to hold preset weights
if "levy_elec_shares" not in st.session_state.keys():
    st.session_state["levy_elec_shares"], _, _ = get_preset_weights(
        "Status quo",
        denominator_values["customers_elec"],
        denominator_values["customers_gas"],
    )
if "levy_gas_shares" not in st.session_state.keys():
    _, st.session_state["levy_gas_shares"], _ = get_preset_weights(
        "Status quo",
        denominator_values["customers_elec"],
        denominator_values["customers_gas"],
    )
if "levy_fixed_shares" not in st.session_state.keys():
    _, _, st.session_state["levy_fixed_shares"] = get_preset_weights(
        "Status quo",
        denominator_values["customers_elec"],
        denominator_values["customers_gas"],
    )

# Show selectors for rebalancing scenario in sidebar
with st.sidebar:
    st.info(
        "**Create your own rebalancing scenario** by adjusting the settings below. *Note: You can manually hide or adjust the width of this sidebar.*"
    )

    # User input: Preset or custom weights
    st.subheader("1. Choose rebalancing or removal for each levy")

    def update_weights_for_selection(customers_elec, customers_gas):
        (
            st.session_state["levy_elec_shares"],
            st.session_state["levy_gas_shares"],
            st.session_state["levy_fixed_shares"],
        ) = get_preset_weights(
            st.session_state["preset"], customers_elec, customers_gas
        )

    preset_options = [
        "Status quo",
        "All gas, status quo fixed or variable",
        "All electricity, status quo fixed or variable",
        "Status quo gas and electricity, all fixed",
        "Status quo gas and electricity, all variable",
    ]

    # On initialisation this should create a session state
    preset = st.selectbox(
        "Do you want to start with a preset approach?",
        preset_options,
        index=0,
        key="preset",
        on_change=update_weights_for_selection,
        args=(
            denominator_values["customers_elec"],
            denominator_values["customers_gas"],
        ),
    )

    st.markdown(
        "*For each policy cost scheme, you have the option to (a) rebalance between electricity and gas, then rebalance between fixed (standing charge) and variable (unit cost) charging, or (b) remove policy cost off of energy bills.*"
    )

    # Create dictionaries for rebalancing weights
    new_electricity_weights = {}
    new_fixed_electricity_weights = {}
    new_variable_electricity_weights = {}
    new_gas_weights = {}
    new_fixed_gas_weights = {}
    new_variable_gas_weights = {}
    new_tax_weights = {}

    # User inputs: Rebalancing weights for each levy
    for levy in levies:
        st.markdown(f"**{levy.name}**")

        mode = st.radio(
            f"Rebalance or remove {levy.short_name.upper()}",
            [
                "Rebalance between electricity and gas",
                "Remove off bills to general taxation",
            ],
            index=0,
            key=f"{levy.short_name}_radio",
        )

        if (
            st.session_state[f"{levy.short_name}_radio"]
            == "Rebalance between electricity and gas"
        ):
            new_tax_weights[levy.short_name] = 0
            new_gas_weights[levy.short_name] = st.slider(
                f"{levy.short_name.upper()}: electricity (0) <-> gas (100)",
                value=st.session_state["levy_gas_shares"].get(levy.short_name),
                key=f"{levy.short_name}_gas_weights",
            )
            new_electricity_weights[levy.short_name] = (
                100 - new_gas_weights[levy.short_name]
            )
        else:
            new_electricity_weights[levy.short_name] = 0
            new_gas_weights[levy.short_name] = 0
            new_tax_weights[levy.short_name] = 100

        # Summation check
        if (
            new_electricity_weights.get(levy.short_name)
            + new_gas_weights.get(levy.short_name)
            + new_tax_weights.get(levy.short_name)
            != 100
        ):
            st.error(f"Please ensure percentage weights add up to 100 for {levy.name}.")

        # User input: Electricity, fixed vs variable
        if new_electricity_weights[levy.short_name] > 0:
            new_fixed_electricity_weights[levy.short_name] = st.slider(
                f"{levy.short_name.upper()} electricity: unit cost (0) <-> standing charge (100)",
                value=st.session_state["levy_fixed_shares"].get(levy.short_name),
                key=f"{levy.short_name}_electricity_fixed_shares",
            )
            new_variable_electricity_weights[levy.short_name] = (
                100 - new_fixed_electricity_weights[levy.short_name]
            )
        else:
            new_fixed_electricity_weights[levy.short_name] = 0
            new_variable_electricity_weights[levy.short_name] = 0

        # User input: Gas, fixed vs variable
        if new_gas_weights[levy.short_name] > 0:
            new_fixed_gas_weights[levy.short_name] = st.slider(
                f"{levy.short_name.upper()} gas: unit cost (0) <-> standing charge (100)",
                value=st.session_state["levy_fixed_shares"].get(levy.short_name),
                key=f"{levy.short_name}_gas_fixed_shares",
            )
            new_variable_gas_weights[levy.short_name] = (
                100 - new_fixed_gas_weights[levy.short_name]
            )
        else:
            new_fixed_gas_weights[levy.short_name] = 0
            new_variable_gas_weights[levy.short_name] = 0

    # User input: Payment method
    st.subheader("2. Choose payment method")
    tariff_payment_method = st.selectbox(
        "Payment method:",
        ["Prepayment meter", "Standard Credit", "Other payment method (Direct debit)"],
        index=2,
        key="tariff_payment_method",
    )

    # Reset button
    def reset_selection():
        # Delete the session states for the widgets
        # This should force them to re-initialise
        st.session_state["preset"] = "Status quo"

        for levy in levies:
            st.session_state[f"{levy.short_name}_radio"] = (
                "Rebalance between electricity and gas"
            )

        st.session_state["tariff_payment_method"] = (
            "Other payment method (Direct debit)"
        )
        st.session_state["levy_elec_shares"], _, _ = get_preset_weights(
            "Status quo",
            denominator_values["customers_elec"],
            denominator_values["customers_gas"],
        )
        _, st.session_state["levy_gas_shares"], _ = get_preset_weights(
            "Status quo",
            denominator_values["customers_elec"],
            denominator_values["customers_gas"],
        )
        _, _, st.session_state["levy_fixed_shares"] = get_preset_weights(
            "Status quo",
            denominator_values["customers_elec"],
            denominator_values["customers_gas"],
        )

        for levy in levies:
            st.session_state[f"{levy.short_name}_gas_weights"] = st.session_state[
                "levy_gas_shares"
            ].get(levy.short_name)
            st.session_state[f"{levy.short_name}_electricity_fixed_shares"] = (
                st.session_state["levy_fixed_shares"].get(levy.short_name)
            )
            st.session_state[f"{levy.short_name}_gas_fixed_shares"] = st.session_state[
                "levy_fixed_shares"
            ].get(levy.short_name)

    st.button("**Reset all settings**", on_click=reset_selection)

# Create dictionary of rebalancing scenario weights
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

# Create bill objects
elec_bills, gas_bills = get_bills(
    tariff_payment_method, scenario_name, elec_tariff_data, gas_tariff_data
)

# Update baseline bill policy costs to match denominator adjusted policy costs
elec_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, True, False) for levy in levies]
)
elec_bills["baseline"].pc = sum(
    [levy.calculate_levy(1, 0, False, False) for levy in levies]
)
gas_bills["baseline"].pc_nil = sum(
    [levy.calculate_levy(0, 0, False, True) for levy in levies]
)
gas_bills["baseline"].pc = sum(
    [levy.calculate_levy(0, 1, False, False) for levy in levies]
)

# Generate scenario results dataframe
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

scenario_bill_outputs = process_rebalancing_scenario_bills(
    elec_bills,
    gas_bills,
    levies,
    weights,
    denominators,
    ofgem_archetypes_df,
    "AnnualConsumptionProfile",
    "ElectricitySingleRatekWh",
    "GaskWh",
    1_000,
    True,
)

scenario_outputs = pd.concat([scenario_outputs, scenario_bill_outputs])

# Create summary pivot table for chart
summary_data = scenario_outputs.pivot_table(
    index=[
        "AnnualConsumptionProfile",
        "scenario",
    ],
    columns="variable",
    values="value",
    aggfunc="sum",
).reset_index()
summary_data = summary_data[
    [
        "AnnualConsumptionProfile",
        "scenario",
        "ArchetypeHeatingFuel",
        "ArchetypeNickname",
        "ArchetypeSize",
        "ElectricitySingleRatekWh",
        "GaskWh",
        "GrossAnnualHouseholdIncome",
        "electricity fixed levy costs",
        "electricity variable levy costs",
        "gas fixed levy costs",
        "gas variable levy costs",
        "total levy costs",
        "electricity bill incl VAT",
        "gas bill incl VAT",
        "total bill incl VAT",
    ]
]
### TO DO: Re-name column headers

# Calculate electricity to gas unit cost and ratios
unit_costs = [
    elec_bills.get("baseline").calculate_variable_consumption(1),
    gas_bills.get("baseline").calculate_variable_consumption(1),
    elec_bills.get(scenario_name).calculate_variable_consumption(1),
    gas_bills.get(scenario_name).calculate_variable_consumption(1),
]
unit_costs = [unit_cost / 1000 for unit_cost in unit_costs]
scenarios = ["Baseline", "Baseline", scenario_name, scenario_name]
fuel = ["Electricity", "Gas", "Electricity", "Gas"]

unit_cost_data = pd.DataFrame(
    {"Scenario": scenarios, "Fuel": fuel, "Unit cost (£/kWh)": unit_costs}
)

ratios = [
    elec_bills.get("baseline").calculate_variable_consumption(1)
    / gas_bills.get("baseline").calculate_variable_consumption(1),
    elec_bills.get(scenario_name).calculate_variable_consumption(1)
    / gas_bills.get(scenario_name).calculate_variable_consumption(1),
]
ratio_scenarios = ["Baseline", scenario_name]
ratio_data = pd.DataFrame(
    {"Scenario": ratio_scenarios, "Electricity to gas unit cost ratio": ratios}
)

# Print unit cost summary chart
st.subheader("Rebalanced scenario: Electricity and gas unit costs")

cmap_1 = {"Electricity": "#18a48c", "Gas": "#0000ff"}

# Stacked bar chart option
# unit_cost_chart = (
#     alt.Chart(unit_cost_data)
#     .mark_bar()
#     .encode(
#         y="Scenario:N",
#         x="Unit cost (£/kWh):Q",
#         color=alt.Color(
#             "Fuel",
#             scale=alt.Scale(domain=list(cmap_1.keys()), range=list(cmap_1.values())),
#         ),
#     )
# ).properties(width=800)

# Grouped bar chart option
unit_base_chart = (
    alt.Chart(unit_cost_data)
    .mark_bar()
    .encode(
        x="Unit cost (£/kWh):Q",
        y="Scenario:N",
        color=alt.Color(
            "Fuel",
            scale=alt.Scale(domain=list(cmap_1.keys()), range=list(cmap_1.values())),
        ),
    )
    .properties(width=800)
)
unit_labels = unit_base_chart.mark_text(
    align="center", baseline="middle", dx=15
).encode(
    text=alt.Text("Unit cost (£/kWh):Q", format=".2f"),
    color=alt.value("black"),
)
unit_cost_chart = (unit_base_chart + unit_labels).facet(
    row=alt.Row("Fuel:N", title=None, header=alt.Header(labels=False))
)
unit_cost_chart = unit_cost_chart.configure_axis(
    labelColor="black", titleColor="black"
).configure_legend(labelColor="black", titleColor="black")
st.altair_chart(unit_cost_chart)

# Print ratio chart
bar_chart = (
    alt.Chart(ratio_data)
    .mark_bar(color="#0f294a")
    .encode(y="Scenario:N", x="Electricity to gas unit cost ratio:Q")
    .properties(width=800)
)
bar_labels = bar_chart.mark_text(align="left", baseline="middle", dx=3).encode(
    text=alt.Text("Electricity to gas unit cost ratio:Q", format=".2f")
)
ratio_chart = alt.layer(bar_chart, bar_labels)
ratio_chart = ratio_chart.configure_axis(labelColor="black", titleColor="black")
st.altair_chart(ratio_chart)

# Present distributional impacts results
st.subheader("**Rebalanced scenario: Distributional impacts on energy bills**")

# Plot summary chart
baseline_totals = scenario_outputs.loc[
    (scenario_outputs["scenario"] == "Baseline")
    & (scenario_outputs["variable"] == "total bill incl VAT")
]
scenario_totals = scenario_outputs.loc[
    (scenario_outputs["scenario"] == scenario_name)
    & (scenario_outputs["variable"] == "total bill incl VAT")
]
cost_changes = (
    scenario_totals.value.reset_index(drop=True)
    - baseline_totals.value.reset_index(drop=True)
).rename("Bill change")

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

chart = alt.Chart(chart_data)

cmap_2 = {
    "Electricity": "#18a48c",
    "Electricity/Other": "#fdb633",
    "Gas": "#0000ff",
    "Other": "#f6a4b7",
}
points = chart.mark_point(opacity=1, filled=True).encode(
    x=alt.X(
        "Bill change:Q",
        axis=alt.Axis(grid=True),
        title="Bill change from current baseline (£)",
        scale=alt.Scale(domain=[-400, 200]),
    ),
    y=alt.Y(
        "Energy consumer archetype:N",
        axis=alt.Axis(grid=True, labelLimit=500),
        sort=None,
        title="Energy consumer archetype (Lowest (A) to highest (J) income)",
    ),
    size=alt.Size("ArchetypeSize:Q", title="No. of households"),
    color=alt.Color(
        "ArchetypeHeatingFuel:N",
        scale=alt.Scale(domain=list(cmap_2.keys()), range=list(cmap_2.values())),
        title="Main heating fuel",
    ),
)
rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
summary_chart = alt.layer(points, rule).properties(width=800)
summary_chart = summary_chart.configure_axis(
    labelColor="black", titleColor="black"
).configure_legend(labelColor="black", titleColor="black")

# Print distributional effects summary chart
st.altair_chart(summary_chart)
# st.markdown(
#     "*Note: The archetype size for the Typical archetype is arbitrarily set at 1,000,000 households as a placeholder.*"
# )

# Option to view results table
if st.button("View distributional impacts results table"):
    # Show link to distributional effects summary dataframe for download
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False).encode("utf-8")

    csv = convert_df(summary_data)

    st.download_button(
        "Download table",
        csv,
        "rebalanced_scenario_distributional_effect.csv",
        "text/csv",
        key="download-csv",
    )

    st.write(summary_data)

### TO REFACTOR
# Create revenue stream overview dataframe
scenarios = ["Baseline"] + list(weights.keys())
cost_to_elec = [
    sum(
        (status_quo.get(levy.short_name).get("new_electricity_weight")) * levy.revenue
        for levy in levies
    )
] + [
    sum(
        (weights.get(scenario).get(levy.short_name).get("new_electricity_weight"))
        * levy.revenue
        for levy in levies
    )
    for scenario in weights.keys()
]
cost_to_gas = [
    sum(
        (status_quo.get(levy.short_name).get("new_gas_weight")) * levy.revenue
        for levy in levies
    )
] + [
    sum(
        (weights.get(scenario).get(levy.short_name).get("new_gas_weight"))
        * levy.revenue
        for levy in levies
    )
    for scenario in weights.keys()
]
cost_to_tax = [0] + [
    sum(
        (weights.get(scenario).get(levy.short_name).get("new_tax_weight"))
        * levy.revenue
        for levy in levies
    )
    for scenario in weights.keys()
]

divisor = 1_000_000_000
dp = 2
revenue_streams_data = {
    "Scenario": scenarios,
    "Total amount levied on electricity (£ billion)": [
        round(x / divisor, 2) for x in cost_to_elec
    ],
    "Total amount levied on gas (£ billion)": [
        round(x / divisor, 2) for x in cost_to_gas
    ],
    "Total amount removed to general taxation (£ billion)": [
        round(x / divisor, 2) for x in cost_to_tax
    ],
}
revenue_streams_df = pd.DataFrame(revenue_streams_data)

# Print revenue streams summary dataframe
st.subheader("Rebalanced scenario: Total cost to energy bills and general taxation")
st.write(revenue_streams_df)

cost_to_taxpayers = round(revenue_streams_df.iloc[1, 3], 2)
st.markdown(
    f"<p style='color:red;'>Additional annual cost to taxpayers: <b>£{cost_to_taxpayers} billion</b></p>",
    unsafe_allow_html=True,
)
