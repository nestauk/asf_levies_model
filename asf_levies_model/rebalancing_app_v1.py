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

from summary import process_rebalancing_scenarios, process_rebalancing_scenario_bills

from utils.st_components import get_preset_weights, get_bills

st.title("Policy cost levies rebalancing model V1")

### DOWNLOADING DATA ###
st.subheader(
    "**Downloading latest Ofgem policy cost and price cap data**", divider=True
)


@st.cache_data
def load_annex_4():
    return download_annex_4(as_fileobject=True)


# Download Annex 4 data and initialise levy objects
with st.spinner("Downloading latest Ofgem policy cost data..."):
    fileobject_annex4 = load_annex_4()
    levies = [
        RO.from_dataframe(process_data_RO(fileobject_annex4), denominator=94_200_366),
        AAHEDC.from_dataframe(
            process_data_AAHEDC(fileobject_annex4), denominator=94_200_366
        ),
        GGL.from_dataframe(process_data_GGL(fileobject_annex4), denominator=24_503_683),
        WHD.from_dataframe(process_data_WHD(fileobject_annex4)),
        ECO.from_dataframe(process_data_ECO(fileobject_annex4)),
        FIT.from_dataframe(process_data_FIT(fileobject_annex4), revenue=689_233_317),
    ]
    fileobject_annex4.close()
st.success("Latest policy cost data downloaded!")


@st.cache_data
def load_annex_9():
    return download_annex_9(as_fileobject=True)


# Download Annex 9 data
with st.spinner("Downloading latest Ofgem price cap data..."):
    fileobject = load_annex_9()
    # Other payment
    elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
    elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
    gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
    gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
    # Prepayment meter
    elec_ppm_nil = process_tariff_elec_ppm_nil(fileobject)
    elec_ppm_typical = process_tariff_elec_ppm_typical(fileobject)
    gas_ppm_nil = process_tariff_gas_ppm_nil(fileobject)
    gas_ppm_typical = process_tariff_gas_ppm_typical(fileobject)
    # Standard Credit
    elec_standard_credit_nil = process_tariff_elec_standard_credit_nil(fileobject)
    elec_standard_credit_typical = process_tariff_elec_standard_credit_typical(
        fileobject
    )
    gas_standard_credit_nil = process_tariff_gas_standard_credit_nil(fileobject)
    gas_standard_credit_typical = process_tariff_gas_standard_credit_typical(fileobject)
    fileobject.close()
st.success("Latest final levelised price cap data downloaded!")

# Create dictionaries of tariff data
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


# Load energy consumption profiles
@st.cache_data
def load_archetypes():
    return ofgem_archetypes_data()


ofgem_archetypes_df = load_archetypes()

### USER INPUT: SCENARIO NAME ###
# Take rebalancing scenario name
st.subheader("**What would you like to call your rebalancing scenario?**", divider=True)
scenario_name = st.text_input("Enter scenario name")
if not scenario_name:
    st.error("Please provide a scenario name.")


### USER INPUT: DENOMINATORS ###
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

### Rebalance Baseline levies to reflect denominator choices.
# We can't meaningfully replicate ofgem's levy denominators exactly, so we'll first rebalance
# the levy baseline so that comparisons are internally consistent.
# This will lead to different bill amounts to those published by ofgem.

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

# manually update WHD weights according to denominator balance
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

# Rebalance status quo
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

### USER INPUT: REBALANCING WEIGHTS ###
st.subheader(
    "**What percentage of each levy revenue should be reapportioned to :blue[electricity], :red[gas] and :violet[general taxation]?**",
    divider=True,
)

# Take user input for preset preference
st.write("**Would you like to use your own or preset rebalancing values?**")
preset = st.selectbox(
    "Use rebalancing weights:",
    (
        "My own",
        "Status quo",
        "All gas, status quo fixed or variable",
        "All electricity, status quo fixed or variable",
        "Status quo gas and electricity, all fixed",
        "Status quo gas and electricity, all variable",
    ),
)

levy_elec_shares, levy_gas_shares, levy_fixed_shares = get_preset_weights(
    preset, customers_elec, customers_gas
)

# Take rebalancing weights for electricity/gas/tax
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**:blue[Electricity]**")
    new_electricity_weights = {}
    for levy in levies:
        new_electricity_weights[levy.short_name] = st.number_input(
            f"{levy.name} electricity weight (%): ",
            0,
            100,
            value=levy_elec_shares.get(levy.short_name),
        )
with col2:
    st.markdown("**:red[Gas]**")
    new_gas_weights = {}
    for levy in levies:
        new_gas_weights[levy.short_name] = st.number_input(
            f"{levy.name} gas weight (%): ",
            0,
            100,
            value=levy_gas_shares.get(levy.short_name),
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
                f"Electricity, fixed weight ({levy.short_name.upper()}) (%)",
                value=levy_fixed_shares.get(levy.short_name),
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
                f"Gas, fixed weight ({levy.short_name.upper()}) (%)",
                value=levy_fixed_shares.get(levy.short_name),
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

# Initialise rebalancing weights
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

### USER INPUT: PAYMENT METHOD ###
st.subheader("**Which payment method type would you like to model?**", divider=True)
tariff_payment_method = st.selectbox(
    "Payment by:", ("Prepayment meter", "Standard Credit", "Other payment method")
)

# Create bill objects
elec_bills, gas_bills = get_bills(
    tariff_payment_method, scenario_name, elec_tariff_data, gas_tariff_data
)

### Update baseline bill policy costs to match denominator adjusted policy costs.
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

### USER INPUT: GENERATE SCENARIO RESULTS ###
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

    st.subheader("**Summary**", divider=True)

    st.markdown(
        "**Amount not levied on energy (e.g. to be raised via general taxation)**"
    )
    for levy in levies:
        st.markdown(
            f"{levy.name}: £{((new_tax_weights.get(levy.short_name)/100)*levy.revenue)/1_000_000_000} billion."
        )

    st.markdown("**Electricity unit cost to Gas unit cost ratio**")
    baseline_ratio = elec_bills.get("baseline").calculate_variable_consumption(
        1
    ) / gas_bills.get("baseline").calculate_variable_consumption(1)
    scenario_ratio = elec_bills.get(scenario_name).calculate_variable_consumption(
        1
    ) / gas_bills.get(scenario_name).calculate_variable_consumption(1)
    st.markdown(f"Baseline: {baseline_ratio:.2f}")
    st.markdown(f"{scenario_name}: {scenario_ratio:.2f}")

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
    st.markdown(
        "*Hover over the table below to download using the 'Download as CSV' button.*"
    )
    st.write(summary_data)

    # Summary figure - Dot plot
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

    chart_data = chart_data.sort_values(
        "GrossAnnualHouseholdIncome", ascending=True
    ).reset_index(drop=True)

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
            title="Energy consumer archetype (low to high income)",
        ),
        size="ArchetypeSize:Q",
        color="ArchetypeHeatingFuel:N",
    )
    rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
    chart = points + rule.properties(width=800)

    st.altair_chart(chart)
