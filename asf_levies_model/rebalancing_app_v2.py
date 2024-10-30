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
    st.title("Nesta Levies Rebalancing Model")  ### TO DO: Workshop title

with row1_2:
    st.markdown("###")
    st.markdown(
        "This model was created as part of Nesta's project on [making energy cheaper by rebalancing levies](https://www.nesta.org.uk/project/finding-ways-to-deliver-cheaper-electricity-by-rebalancing-levies/)."
    )

# Show selectors for rebalancing scenario in sidebar
with st.sidebar:
    st.info(
        "**Create your own rebalancing scenario.** More information to go here. You can manually hide or adjust the width of the sidebar."
    )

    # # User input: Scenario name
    # st.subheader("1. Name your scenario")
    # st.markdown("Note: Naming it *Baseline* breaks the results table")
    # scenario_name = st.text_input("Enter scenario name:", "My scenario")
    # if not scenario_name:
    #     st.error("Please provide a scenario name.")
    scenario_name = "Rebalanced scenario"

    ### TO DO: Finalise presets
    # User input: Preset or custom weights
    st.subheader("1. Choose rebalancing or removal for each levy")
    preset_options = [
        "My own",
        "Status quo",
        "All gas, status quo fixed or variable",
        "All electricity, status quo fixed or variable",
        "Status quo gas and electricity, all fixed",
        "Status quo gas and electricity, all variable",
    ]
    default_index = preset_options.index("Status quo")
    preset = st.selectbox(
        "Use custom or preset settings:", preset_options, index=default_index
    )
    levy_elec_shares, levy_gas_shares, levy_fixed_shares = get_preset_weights(
        preset,
        denominator_values["customers_elec"],
        denominator_values["customers_gas"],
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
        )
        if mode == "Rebalance between electricity and gas":
            new_tax_weights[levy.short_name] = 0
            new_gas_weights[levy.short_name] = st.slider(
                f"{levy.short_name.upper()}: electricity (0) <-> gas (100)",
                value=levy_gas_shares.get(levy.short_name),
            )
            new_electricity_weights[levy.short_name] = (
                100 - new_gas_weights[levy.short_name]
            )
        else:
            new_electricity_weights[levy.short_name] = 0
            new_gas_weights[levy.short_name] = 0
            new_tax_weights[levy.short_name] = 100

        # ALTERNATIVE BLOCK
        # removal_setting = st.radio(
        #     f"Remove revenue from {levy.short_name.upper()} to general taxation?",
        #     ["No", "Yes"],
        # )
        # if removal_setting == "Yes":
        #     removal_mode = st.radio(
        #         f"Remove {levy.short_name.upper()} revenue as percentage or amount:",
        #         ["Percentage", "Amount"],
        #     )
        #     if removal_mode == "Percentage":
        #         new_tax_weights[levy.short_name] = st.number_input(
        #             f"{levy.short_name.upper()} tax (%): ", 0, 100, 100
        #         )
        #         if new_tax_weights[levy.short_name] == 100:
        #             new_electricity_weights[levy.short_name] = 0
        #             new_gas_weights[levy.short_name] = 0
        #         else:
        #             new_gas_weights[levy.short_name] = st.slider(
        #                 f"{levy.short_name.upper()}: electricity <-> gas",
        #                 min_value=0,
        #                 max_value=100 - new_tax_weights[levy.short_name],
        #             )
        #             new_electricity_weights[levy.short_name] = (
        #                 100 - new_gas_weights[levy.short_name]
        #             )
        #     else:
        #         removal_amount = st.number_input(
        #             f"{levy.short_name.upper()} revenue to remove: "
        #         )
        #         new_tax_weights[levy.short_name] = removal_amount / levy.revenue
        #         if new_tax_weights[levy.short_name] == 100:
        #             new_electricity_weights[levy.short_name] = 0
        #             new_gas_weights[levy.short_name] = 0
        #         else:
        #             new_gas_weights[levy.short_name] = st.slider(
        #                 f"{levy.short_name.upper()}: electricity <-> gas",
        #                 min_value=0,
        #                 max_value=100 - new_tax_weights[levy.short_name],
        #             )
        #             new_electricity_weights[levy.short_name] = (
        #                 100 - new_gas_weights[levy.short_name]
        #             )
        # else:
        #     new_tax_weights[levy.short_name] = 0
        #     new_gas_weights[levy.short_name] = st.slider(
        #         f"{levy.short_name.upper()}: electricity (0) <-> gas (100)",
        #         value=levy_gas_shares.get(levy.short_name),
        #     )
        #     new_electricity_weights[levy.short_name] = (
        #         100 - new_gas_weights[levy.short_name]
        #     )

        # ALTERNATIVE BLOCK
        # col1, col2, col3 = st.columns(3)
        # with col1:
        #     new_electricity_weights[levy.short_name] = st.number_input(
        #         f"{levy.short_name.upper()} electricity (%): ",
        #         0,
        #         100,
        #         value=levy_elec_shares.get(levy.short_name),
        #     )
        # with col2:
        #     new_gas_weights[levy.short_name] = st.number_input(
        #         f"{levy.short_name.upper()} gas (%): ",
        #         0,
        #         100,
        #         value=levy_gas_shares.get(levy.short_name),
        #     )
        # with col3:
        #     new_tax_weights[levy.short_name] = st.number_input(
        #         f"{levy.short_name.upper()} tax (%): ", 0, 100
        #     )

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
                f"{levy.short_name.upper()} electricity: variable (0) <-> fixed (100)",
                value=levy_fixed_shares.get(levy.short_name),
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
                f"{levy.short_name.upper()} gas: variable (0) <-> fixed (100)",
                value=levy_fixed_shares.get(levy.short_name),
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
        ("Prepayment meter", "Standard Credit", "Other payment method"),
    )

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
points = chart.mark_point(opacity=1, filled=True).encode(
    x=alt.X(
        "Bill change:Q",
        axis=alt.Axis(grid=True),
        title="Bill change from current baseline (£)",
    ),
    y=alt.Y(
        "Energy consumer archetype:N",
        axis=alt.Axis(grid=True, labelLimit=500),
        sort=None,
        title="Energy consumer archetype",
    ),
    size="ArchetypeSize:Q",
    color="ArchetypeHeatingFuel:N",
)
rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
chart = points + rule.properties(width=800)

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
unit_cost_chart = (
    alt.Chart(unit_cost_data)
    .mark_bar()
    .encode(y="Scenario:N", x="Unit cost (£/kWh):Q", color="Fuel")
).properties(width=800)
st.altair_chart(unit_cost_chart)

# Print ratio chart
ratio_chart = (
    alt.Chart(ratio_data)
    .mark_bar()
    .encode(y="Scenario:N", x="Electricity to gas unit cost ratio:Q")
    .properties(width=800)
)
st.altair_chart(ratio_chart)


# Print distributional effects summary chart
st.subheader("**Rebalanced scenario: Distributional effects on energy bills**")
st.altair_chart(chart)

# Print distributional effects summary dataframe for download
# st.markdown(
#     "*Hover over the table below to download using the 'Download as CSV' button.*"
# )
# st.write(summary_data)

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

revenue_streams_data = {
    "Scenario": scenarios,
    "Total cost levied on electricity": cost_to_elec,
    "Total cost levied on gas": cost_to_gas,
    "Total cost to general taxation": cost_to_tax,
}
revenue_streams_df = pd.DataFrame(revenue_streams_data)

# Print revenue streams summary dataframe
st.subheader("Rebalanced scenario: Total revenue streams")
st.write(revenue_streams_df)
