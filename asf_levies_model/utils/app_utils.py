import streamlit as st
import pandas as pd
import altair as alt

from typing import List, Dict

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
    process_tariff_elec_ppm_nil,
    process_tariff_elec_ppm_typical,
    process_tariff_gas_ppm_nil,
    process_tariff_gas_ppm_typical,
    process_tariff_elec_standard_credit_nil,
    process_tariff_elec_standard_credit_typical,
    process_tariff_gas_standard_credit_nil,
    process_tariff_gas_standard_credit_typical,
    ofgem_archetypes_data,
)

from asf_levies_model.levies import Levy, RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.consumers import Consumer

from asf_levies_model.summary import (
    create_scenario_weights_dict,
    set_common_denominators,
)


def instantiate_levies(
    supply_elec: float = 94200366.0,  # MWh
    supply_gas: float = 265197947.0,  # MWh
    customers_elec: int = 24_503_683,
    customers_gas: int = 29_078_770,
) -> List:

    # Scaling factor for estimating domestic share of FIT revenue
    total_supply_elec = (
        250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
    )
    exempt_eii_supply = (
        9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
    )
    fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

    # Instantiate status quo levies with Annex 4 data
    @st.cache_data
    def load_annex_4():
        return download_annex_4(as_fileobject=True)

    fileobject = load_annex_4()
    levies = [
        RO.from_dataframe(process_data_RO(fileobject), denominator=supply_elec),
        AAHEDC.from_dataframe(process_data_AAHEDC(fileobject), denominator=supply_elec),
        GGL.from_dataframe(process_data_GGL(fileobject), denominator=customers_gas),
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
    fileobject.close()

    # Create dictionary of denominators for each levy
    denominators = set_common_denominators(
        levies, supply_elec, supply_gas, customers_gas, customers_elec
    )
    status_quo = create_scenario_weights_dict(levies)

    # Rebalance baseline levies to reflect denominators
    levies = [
        levy.rebalance_levy(
            **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
        )
        for levy in levies
    ]

    return levies


def get_approach_weights(levies: List, approach_name: str) -> Dict:

    # "Current"
    baseline_weights = create_scenario_weights_dict(levies)

    # "Rebalance all levies on electricity to gas"
    all_gas_weights = create_scenario_weights_dict(levies)
    for levy in [levy for levy in levies if levy.electricity_weight > 0]:
        all_gas_weights[levy.short_name] = {
            "new_electricity_weight": 0,
            "new_gas_weight": 1,
            "new_tax_weight": 0,
            "new_variable_weight_elec": 0,
            "new_fixed_weight_elec": 0,
            "new_variable_weight_gas": levy.electricity_variable_weight,
            "new_fixed_weight_gas": levy.electricity_fixed_weight,
        }

    # "Rebalance RO and FIT levies from electricity to gas"
    rebalance_ro_fit_weights = create_scenario_weights_dict(levies)
    for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
        rebalance_ro_fit_weights[levy.short_name] = {
            "new_electricity_weight": 0,
            "new_gas_weight": 1,
            "new_tax_weight": 0,
            "new_variable_weight_elec": 0,
            "new_fixed_weight_elec": 0,
            "new_variable_weight_gas": levy.electricity_variable_weight,
            "new_fixed_weight_gas": levy.electricity_fixed_weight,
        }

    # "Remove all levies on electricity to taxation"
    sq_electricity_removal_weights = create_scenario_weights_dict(levies)
    for levy in [levy.short_name for levy in levies if levy.electricity_weight > 0]:
        sq_electricity_removal_weights[levy]["new_tax_weight"] = (
            sq_electricity_removal_weights[levy]["new_electricity_weight"]
        )

        for weight_type in [
            "new_electricity_weight",
            "new_variable_weight_elec",
            "new_fixed_weight_elec",
        ]:
            sq_electricity_removal_weights[levy][weight_type] = 0

    # "Remove RO and FIT levies from electricity to taxation"
    remove_ro_fit_weights = create_scenario_weights_dict(levies)
    for levy in ["ro", "fit"]:
        remove_ro_fit_weights[levy]["new_tax_weight"] = remove_ro_fit_weights[levy][
            "new_electricity_weight"
        ]

        for weight_type in [
            "new_electricity_weight",
            "new_variable_weight_elec",
            "new_fixed_weight_elec",
        ]:
            remove_ro_fit_weights[levy][weight_type] = 0

    # Create lookup dictionary for weights of each approach
    approach_weights = {
        "Current": baseline_weights,
        "Rebalance all levies on electricity to gas": all_gas_weights,
        "Rebalance RO and FIT levies from electricity to gas": rebalance_ro_fit_weights,
        "Remove all levies on electricity to taxation": sq_electricity_removal_weights,
        "Remove RO and FIT levies from electricity to taxation": remove_ro_fit_weights,
    }

    if approach_name not in approach_weights.keys():
        raise ValueError("Rebalancing approach name not recognised.")

    return approach_weights[approach_name]


def instantiate_tariffs(payment_method: str = "Other Payment") -> List:

    # Load Annex 9
    @st.cache_data
    def load_annex_9():
        return download_annex_9(as_fileobject=True)

    fileobject_annex_9 = load_annex_9()

    # Load tariff tables from Annex 9
    # Other payment
    elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject_annex_9)
    elec_other_payment_typical = process_tariff_elec_other_payment_typical(
        fileobject_annex_9
    )
    gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject_annex_9)
    gas_other_payment_typical = process_tariff_gas_other_payment_typical(
        fileobject_annex_9
    )
    # Prepayment meter
    elec_ppm_nil = process_tariff_elec_ppm_nil(fileobject_annex_9)
    elec_ppm_typical = process_tariff_elec_ppm_typical(fileobject_annex_9)
    gas_ppm_nil = process_tariff_gas_ppm_nil(fileobject_annex_9)
    gas_ppm_typical = process_tariff_gas_ppm_typical(fileobject_annex_9)
    # Standard Credit
    elec_standard_credit_nil = process_tariff_elec_standard_credit_nil(
        fileobject_annex_9
    )
    elec_standard_credit_typical = process_tariff_elec_standard_credit_typical(
        fileobject_annex_9
    )
    gas_standard_credit_nil = process_tariff_gas_standard_credit_nil(fileobject_annex_9)
    gas_standard_credit_typical = process_tariff_gas_standard_credit_typical(
        fileobject_annex_9
    )
    fileobject_annex_9.close()

    # Instantiate Tariff objects
    if payment_method == "Other Payment":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_other_payment_nil, elec_other_payment_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(
            gas_other_payment_nil, gas_other_payment_typical
        )
    elif payment_method == "PPM":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_ppm_nil, elec_ppm_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(gas_ppm_nil, gas_ppm_typical)
    elif payment_method == "Standard Credit":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_standard_credit_nil, elec_standard_credit_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(
            gas_standard_credit_nil, gas_standard_credit_typical
        )
    else:
        raise ValueError("Payment method not recognised.")

    return [electricity_tariff, gas_tariff]


def update_electricity_tariff_policy_cost(tariff, levies):
    tariff.pc_nil = sum([levy.calculate_levy(0, 0, True, False) for levy in levies])
    tariff.pc = sum([levy.calculate_levy(1, 0, False, False) for levy in levies])
    return tariff


def update_gas_tariff_policy_cost(tariff, levies):
    tariff.pc_nil = sum([levy.calculate_levy(0, 0, False, True) for levy in levies])
    tariff.pc = sum([levy.calculate_levy(0, 1, False, False) for levy in levies])
    return tariff


def instantiate_archetype_consumers(gas_tariff, electricity_tariff):

    # Load Ofgem energy consumer archetypes data
    @st.cache_data
    def load_archetypes():
        return ofgem_archetypes_data()

    ofgem_archetypes_df = load_archetypes()

    # Create list of Consumers (Average Ofgem archetypes only, n=24)
    consumers = [
        Consumer.consumer_from_dataframe(
            df=ofgem_archetypes_df,
            row=row,
            name_col="AnnualConsumptionProfile",
            archetype_col="AnnualConsumptionProfile",
            net_annual_income_col="NetAnnualHouseholdIncome",
            main_heating_fuel_col="ArchetypeHeatingFuel",
            gas_consumption_col="GaskWh",
            electricity_consumption_col="ElectricitySingleRatekWh",
            gas_tariff=gas_tariff,
            electricity_tariff=electricity_tariff,
            unit_converter=1_000,
            size_col="ArchetypeSize",
        )
        for row in range(1, 25)
    ]

    return consumers


def calculate_unit_cost_ratio(electricity_tariff, gas_tariff):
    return electricity_tariff.calculate_variable_consumption(
        1
    ) / gas_tariff.calculate_variable_consumption(1)


def instantiate_new_levy(
    new_levy_name,
    new_levy_revenue,
    new_levy_fuel,
    new_levy_type,
    supply_elec,
    customers_elec,
    supply_gas,
    customers_gas,
):

    electricity_fixed_weight = (
        1
        if (new_levy_fuel == "Electricity") & (new_levy_type == "Standing charge")
        else 0
    )
    electricity_variable_weight = (
        1 if (new_levy_fuel == "Electricity") & (new_levy_type == "Consumption") else 0
    )
    gas_variable_weight = (
        1 if (new_levy_fuel == "Gas") & (new_levy_type == "Consumption") else 0
    )
    gas_fixed_weight = (
        1 if (new_levy_fuel == "Gas") & (new_levy_type == "Standing charge") else 0
    )

    new_levy = Levy(
        name=new_levy_name,
        short_name=new_levy_name,
        electricity_weight=1 if new_levy_fuel == "Electricity" else 0,
        gas_weight=1 if new_levy_fuel == "Gas" else 0,
        tax_weight=0,
        electricity_variable_weight=electricity_variable_weight,
        electricity_fixed_weight=electricity_fixed_weight,
        gas_variable_weight=gas_variable_weight,
        gas_fixed_weight=gas_fixed_weight,
        electricity_variable_rate=(new_levy_revenue / supply_elec)
        * electricity_variable_weight,
        electricity_fixed_rate=(new_levy_revenue / customers_elec)
        * electricity_fixed_weight,
        gas_variable_rate=(new_levy_revenue / supply_gas) * gas_variable_weight,
        gas_fixed_rate=(new_levy_revenue / customers_gas) * gas_fixed_weight,
        general_taxation=0,
        revenue=new_levy_revenue,
        price_cap_period="LATEST",
    )

    return new_levy


def get_tidy_summary(consumers, scenario_name):
    tidy_summary = pd.concat([consumer.get_tidy_summary() for consumer in consumers])
    tidy_summary["Scenario"] = scenario_name
    return tidy_summary


def tidy_to_pivot_summary(tidy_summary):
    pivot_summary_table = tidy_summary.pivot_table(
        index=["Name", "Scenario"], columns="Attribute", values="Value", aggfunc="first"
    ).reset_index()
    pivot_summary_table = pivot_summary_table[
        [
            "Name",
            "Scenario",
            "main_heating_fuel",
            "size",
            "electricity_bill",
            "gas_bill",
            "combined_fuel_bill",
        ]
    ].sort_values(by=["Scenario", "Name"])
    return pivot_summary_table


def make_archetype_bill_change_chart(rebalanced_summary_table):

    # Fuel colours
    cmap_2 = {
        "Electricity": "#18a48c",
        "Electricity/Other": "#fdb633",
        "Gas": "#0000ff",
        "Other": "#f6a4b7",
    }

    chart = alt.Chart(rebalanced_summary_table)
    # Dots
    points = chart.mark_point(opacity=1, filled=True).encode(
        x=alt.X(
            "bill_change:Q",
            axis=alt.Axis(grid=True),
            title="Bill change from baseline (£)",
            scale=alt.Scale(domain=[-400, 200]),
        ),
        y=alt.Y(
            "Name:N",
            axis=alt.Axis(grid=True, labelLimit=500),
            sort=None,
            title="Energy consumer archetype (Lowest (A) to highest (J) income)",
        ),
        size=alt.Size("size:Q", title="No. of households"),
        color=alt.Color(
            "main_heating_fuel:N",
            scale=alt.Scale(domain=list(cmap_2.keys()), range=list(cmap_2.values())),
            title="Main heating fuel",
        ),
    )
    # x=0 base line
    rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
    # Layer dots and line
    chart = alt.layer(points, rule).properties(width=1000)
    chart = chart.configure_axis(
        labelColor="black", titleColor="black"
    ).configure_legend(labelColor="black", titleColor="black")

    return chart
