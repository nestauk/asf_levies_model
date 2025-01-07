import streamlit as st

from asf_levies_model.utils.app_utils import (
    instantiate_levies,
    get_approach_weights,
    instantiate_tariffs,
    update_electricity_tariff_policy_cost,
    update_gas_tariff_policy_cost,
    instantiate_archetype_consumers,
    calculate_unit_cost_ratio,
    instantiate_new_levy,
    get_tidy_summary,
    tidy_to_pivot_summary,
    make_archetype_bill_change_chart,
)

from asf_levies_model.summary import set_common_denominators

st.set_page_config(
    page_title="Nesta Levies Rebalancing Model", page_icon="🏠", layout="wide"
)

# Instantiate baseline levies
levies = instantiate_levies()

# Create dictionary of denominators for each levy
supply_elec = 94200366.0
supply_gas = 265197947.0
customers_elec = 24_503_683
customers_gas = 29_078_770

denominators = set_common_denominators(
    levies,
    supply_elec=supply_elec,
    supply_gas=supply_gas,
    customers_elec=customers_elec,
    customers_gas=customers_gas,
)

# Show selectors for levy reform scenario in side bar
with st.sidebar:
    st.info("**Test a levy reform scenario** by adjusting the settings below.")

    # User input to choose rebalancing approach
    approach = st.radio(
        "**Rebalancing approach:**",
        [
            "Current",
            "Rebalance all levies on electricity to gas",
            "Rebalance RO and FIT levies from electricity to gas",
            "Remove all levies on electricity to taxation",
            "Remove RO and FIT levies from electricity to taxation",
        ],
        index=0,
    )

    # User input to add a new levy
    new_levy_mode = st.radio("**Add new levy?**", ["Yes", "No"], index=1)

    if new_levy_mode == "Yes":
        new_levy_name = st.text_input("New levy name", value="Test levy")
        new_levy_revenue = st.number_input(
            "Amount to raise (£)", min_value=0, value="min"
        )
        new_levy_fuel = st.radio("Levy on:", ["Electricity", "Gas"])
        new_levy_type = st.radio("Levy on:", ["Consumption", "Standing charge"])


# Rebalance levies based on chosen approach
rebalancing_weights = get_approach_weights(levies, approach)
rebalanced_levies = [
    levy.rebalance_levy(
        **rebalancing_weights.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# Add new levy to list of rebalanced levies if selected
if new_levy_mode == "Yes":
    new_levy = instantiate_new_levy(
        new_levy_name=new_levy_name,
        new_levy_revenue=new_levy_revenue,
        new_levy_fuel=new_levy_fuel,
        new_levy_type=new_levy_type,
        supply_elec=supply_elec,
        customers_elec=customers_elec,
        supply_gas=supply_gas,
        customers_gas=customers_gas,
    )

    rebalanced_levies.append(new_levy)

# Instantiate baseline tariffs
baseline_tariffs = instantiate_tariffs(payment_method="Other Payment")
baseline_electricity_tariff = update_electricity_tariff_policy_cost(
    baseline_tariffs[0], levies
)
baseline_gas_tariff = update_gas_tariff_policy_cost(baseline_tariffs[1], levies)

# Instantiate rebalanced tariffs
rebalanced_tariffs = instantiate_tariffs(payment_method="Other Payment")
rebalanced_electricity_tariff = update_electricity_tariff_policy_cost(
    rebalanced_tariffs[0], rebalanced_levies
)
rebalanced_gas_tariff = update_gas_tariff_policy_cost(
    rebalanced_tariffs[1], rebalanced_levies
)

# Create a list of Consumers (Typical and average Ofgem archetypes only, n=25) for baseline and rebalanced scenario
baseline_consumers = instantiate_archetype_consumers(
    baseline_gas_tariff, baseline_electricity_tariff
)
rebalanced_consumers = instantiate_archetype_consumers(
    rebalanced_gas_tariff, rebalanced_electricity_tariff
)

# Result: Unit cost ratio
baseline_ratio = calculate_unit_cost_ratio(
    baseline_electricity_tariff, baseline_gas_tariff
)
rebalanced_ratio = calculate_unit_cost_ratio(
    rebalanced_electricity_tariff, rebalanced_gas_tariff
)

# Result: Cost to taxpayers
if new_levy_mode == "Yes":
    cost_to_tax = sum(
        rebalancing_weights[levy.short_name]["new_tax_weight"] * levy.revenue
        for levy in rebalanced_levies[:-1]
    )
else:
    cost_to_tax = sum(
        rebalancing_weights[levy.short_name]["new_tax_weight"] * levy.revenue
        for levy in rebalanced_levies
    )

col1, col2, col3 = st.columns(3)
with col2:
    st.warning(
        f"**Electricity-to-gas ratio: {rebalanced_ratio:.2f}** *(Current: {baseline_ratio:.2f})*"
    )
with col3:
    st.error(
        f"**Additional cost to taxpayers: £{cost_to_tax/1_000_000_000:.2f} billion per year**"
    )


# Result: Distribution impacts dot chart
baseline_summary_table = tidy_to_pivot_summary(
    get_tidy_summary(baseline_consumers, "Baseline")
)
rebalanced_summary_table = tidy_to_pivot_summary(
    get_tidy_summary(rebalanced_consumers, "Rebalanced")
)
# Add bill change column
rebalanced_summary_table["bill_change"] = (
    rebalanced_summary_table["combined_fuel_bill"]
    - baseline_summary_table["combined_fuel_bill"]
)

# Result: Distributional impacts
st.markdown(
    f"<p style='color:black; font-size: 20px;'><b>Distributional impacts: Effect on energy bills</b></p>",
    unsafe_allow_html=True,
)
chart = make_archetype_bill_change_chart(rebalanced_summary_table)
st.altair_chart(chart)
