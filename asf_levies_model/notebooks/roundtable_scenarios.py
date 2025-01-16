# %%
import pandas as pd
import copy
from datetime import datetime
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
    ofgem_archetypes_data,
    ofgem_archetypes_scheme_eligibility,
)

from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.summary import (
    _rebalance_levies,
    create_scenario_weights_dict,
    calculate_cost_stream,
    set_common_denominators,
)

from asf_levies_model import config, PROJECT_DIR

from asf_levies_model.consumers import Consumer

# %% [markdown]
#  **Status quo levies from Annex 4**

# %%
# Assign denominator values
supply_elec = 94_200_366
supply_gas = 265_197_947
customers_gas = 24_503_683
customers_elec = 29_078_770

# %%
# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    250_020_739  # DESNZ GB total electricity consumption - all meters (2022)
)
exempt_eii_supply = 9_417_916  # Oct-Dec2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %%
# Instantiate status quo levies with Annex 4 data
fileobject = download_annex_4(as_fileobject=True)
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

# %%
# Create dictionary of denominators for each levy
denominators = set_common_denominators(
    levies, supply_elec, supply_gas, customers_gas, customers_elec
)

# %% [markdown]
#  **Defining rebalancing weights for each scenario**

# %% [markdown]
# Note: All 4 scenarios have an increase in WHD by a factor of 3.0

# %%
uplift_factor = 3.0

# %% [markdown]
# 0. Baseline

# %%
# Scenario 0: Status quo weights which reflect denominators
status_quo_weights = create_scenario_weights_dict(levies)

# %% [markdown]
# 1. Rebalance RO+FiT from Electricity to Gas, increase WHD by a factor of 3.0

# %%
scenario_1_weights = create_scenario_weights_dict(levies)

# Rebalance RO and FIT
for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
    scenario_1_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %% [markdown]
# 2. Rebalance RO+FiT from Electricity to Gas, increase WHD by a factor of 3.0, shift WHD from standing charge to variable (on both electricity and gas)

# %%
scenario_2_weights = create_scenario_weights_dict(levies)

# Rebalance RO and FIT
for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
    scenario_2_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# Change WHD from standing charge to variable
for levy in [levy for levy in levies if levy.short_name in ["whd"]]:
    scenario_2_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,  # maintain proportion of revenue from electricity
        "new_gas_weight": levy.gas_weight,  # maintain proportion of revenue from gas
        "new_tax_weight": 0,
        "new_variable_weight_elec": 1,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": 1,
        "new_fixed_weight_gas": 0,
    }

# %% [markdown]
# 3. Rebalance RO+FiT from Electricity to Gas, Remove ECO from gas to taxation, increase WHD by a factor of 3.0

# %%
scenario_3_weights = create_scenario_weights_dict(levies)

# Rebalance RO and FIT
for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
    scenario_3_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# Remove ECO (gas portion only) to taxation
for levy in [levy for levy in levies if levy.short_name in ["eco"]]:
    scenario_3_weights[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": 0,
        "new_tax_weight": levy.gas_weight,  # reallocate only gas's portion of revenue to taxation
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": 0,
        "new_fixed_weight_gas": 0,
    }

# %% [markdown]
# 4. Rebalance RO+FiT from Electricity to Gas, Remove ECO from gas and electricity to taxation, increase WHD by a factor of 3.0

# %%
scenario_4_weights = create_scenario_weights_dict(levies)

# Rebalance RO and FIT
for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
    scenario_4_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# Remove ECO (fully from gas and electricity) to taxation
for levy in [levy for levy in levies if levy.short_name in ["eco"]]:
    scenario_4_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 0,
        "new_tax_weight": 1,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": 0,
        "new_fixed_weight_gas": 0,
    }

# %%
# Create a dictionary of {scenario name: rebalancing weights}
scenario_weights = {
    "Baseline": status_quo_weights,
    "Scenario 1": scenario_1_weights,
    "Scenario 2": scenario_2_weights,
    "Scenario 3": scenario_3_weights,
    "Scenario 4": scenario_4_weights,
}

# %% [markdown]
#  **Levies for each scenario**

# %%
# Rebalance baseline levies to reflect denominators
levies = [
    levy.rebalance_levy(
        **status_quo_weights.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# %%
# Create new set of levies with uplifted WHD
uplifted_whd_levies = copy.deepcopy(levies)
uplifted_whd_levies[3] = uplifted_whd_levies[3].update_revenue(
    new_revenue=uplifted_whd_levies[3].revenue * uplift_factor,
    **denominators[uplifted_whd_levies[3].short_name],
)

# %%
# Create a dictionary of {scenario name: levies}
scenario_levies = {}

for scenario_name in scenario_weights.keys():
    if scenario_name == "Baseline":
        scenario_levies[scenario_name] = levies
    else:
        scenario_levies[scenario_name] = _rebalance_levies(
            uplifted_whd_levies, scenario_weights, denominators, scenario_name
        )

# %% [markdown]
# **Tariffs for each scenario**

# %%
# Load tariff (Other Payment method) data from Annex 9
fileobject = download_annex_9(as_fileobject=True)
elec_other_payment_nil = process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
# Create a dictionary of {scenario name: tariffs}
elec_tariffs = {}
gas_tariffs = {}
for scenario_name in scenario_weights.keys():
    elec_tariff = ElectricityOtherPayment.from_dataframe(
        elec_other_payment_nil, elec_other_payment_typical
    )
    elec_tariff.name = scenario_name + " " + elec_tariff.name
    elec_tariffs[scenario_name] = elec_tariff

    gas_tariff = GasOtherPayment.from_dataframe(
        gas_other_payment_nil, gas_other_payment_typical
    )
    gas_tariff.name = scenario_name + " " + gas_tariff.name
    gas_tariffs[scenario_name] = gas_tariff

# %%
# Update tariff policy costs with rebalanced levies
for scenario_name in scenario_weights.keys():
    elec_tariffs[scenario_name].pc_nil = sum(
        [
            levy.calculate_levy(0, 0, True, False)
            for levy in scenario_levies[scenario_name]
        ]
    )
    elec_tariffs[scenario_name].pc = sum(
        [
            levy.calculate_levy(1, 0, False, False)
            for levy in scenario_levies[scenario_name]
        ]
    )
    gas_tariffs[scenario_name].pc_nil = sum(
        [
            levy.calculate_levy(0, 0, False, True)
            for levy in scenario_levies[scenario_name]
        ]
    )
    gas_tariffs[scenario_name].pc = sum(
        [
            levy.calculate_levy(0, 1, False, False)
            for levy in scenario_levies[scenario_name]
        ]
    )

# %% [markdown]
#  **Consumers for each scenario**

# %%
# Load archetypes headline data
ofgem_archetypes_df = ofgem_archetypes_data()

# %% [markdown]
# We need to instantiate two sets of archetype Consumers - one set that is eligible and one that is ineligible

# %%
# Creating an input dataframe that has two sets of profiles - eligible and ineligible
ofgem_archetypes_df_eligible = ofgem_archetypes_df.copy(deep=True)
ofgem_archetypes_df_eligible = ofgem_archetypes_df_eligible.iloc[0:25]
ofgem_archetypes_df_eligible["whd_eligible"] = True

ofgem_archetypes_df_ineligible = ofgem_archetypes_df_eligible.copy(deep=True)
ofgem_archetypes_df_ineligible["whd_eligible"] = False

ofgem_archetypes_df_whd_eligibility = pd.concat(
    [ofgem_archetypes_df_eligible, ofgem_archetypes_df_ineligible], ignore_index=True
)

# %%
# Create a dictionary of {scenario name: list of Consumers} (Typical and average Ofgem archetypes only, n=25)
consumers = {}

for scenario_name in scenario_weights.keys():
    consumers[scenario_name] = [
        Consumer.consumer_from_dataframe(
            df=ofgem_archetypes_df_whd_eligibility,
            row=row,
            name_col="AnnualConsumptionProfile",
            archetype_col="AnnualConsumptionProfile",
            net_annual_income_col="NetAnnualHouseholdIncome",
            main_heating_fuel_col="ArchetypeHeatingFuel",
            gas_consumption_col="GaskWh",
            electricity_consumption_col="ElectricitySingleRatekWh",
            gas_tariff=gas_tariffs[scenario_name],
            electricity_tariff=elec_tariffs[scenario_name],
            unit_converter=1_000,
            scheme_eligible_col="whd_eligible",
        )
        for row in range(len(ofgem_archetypes_df_whd_eligibility))
    ]

# Create unique names by modifying name attributes of consumers to reflect eligibility
for scenario_name in scenario_weights.keys():
    for consumer in consumers[scenario_name]:
        if consumer.scheme_eligible == True:
            consumer.name = consumer.name + " Eligible"
        elif consumer.scheme_eligible == False:
            consumer.name = consumer.name + " Ineligible"
        else:
            raise ValueError("No eligibility specified")

# %%
# Apply WHD rebate to eligible consumers
for scenario_name in scenario_weights.keys():
    # Standard £150 rebate in baseline scenario
    if scenario_name == "Baseline":
        for consumer in consumers[scenario_name]:
            if consumer.scheme_eligible == True:
                consumer.apply_social_support_adjustment(
                    adjustment_fuel="electricity",
                    adjustment_parameter=-150,
                    adjustment_mode="flat adjustment",
                    inplace=True,
                )
    else:
        for consumer in consumers[scenario_name]:
            if consumer.scheme_eligible == True:
                consumer.apply_social_support_adjustment(
                    adjustment_fuel="electricity",
                    adjustment_parameter=(-150) * uplift_factor,
                    adjustment_mode="flat adjustment",
                    inplace=True,
                )

# %% [markdown]
# **Results dataframe**

# %%
tidy_summary = pd.DataFrame()
for scenario_name in scenario_weights.keys():
    tidy = pd.concat(
        [consumer.get_tidy_summary() for consumer in consumers[scenario_name]]
    )

    tidy["scenario"] = scenario_name

    tidy_summary = pd.concat([tidy_summary, tidy])

# %%
# Reshaping
scenarios_summary = tidy_summary.pivot_table(
    index=[
        "Name",
        "scenario",
    ],
    columns="Attribute",
    values="Value",
    aggfunc="first",
).reset_index()

# %%
scenarios_summary = scenarios_summary[
    [
        "Name",
        "archetype",
        "scheme_eligible",
        "scenario",
        "main_heating_fuel",
        "electricity_subtotal_bill",  # before rebate
        "gas_subtotal_bill",  # before rebate
        "combined_fuel_bill",  # after rebate
    ]
].sort_values(by=["scenario", "Name"])

# %%
# Create new column for bill change from baseline
baseline = scenarios_summary[scenarios_summary["scenario"] == "Baseline"].set_index(
    "Name"
)["combined_fuel_bill"]

scenarios_summary["Bill change from baseline"] = scenarios_summary.apply(
    lambda row: row["combined_fuel_bill"] - baseline.get(row["Name"], 0),
    axis=1,
)

scenarios_summary = scenarios_summary.reset_index(drop=True)

# %%
# Construct look up table for full archetype and WHD eligible/ineligible size
archetype_size = ofgem_archetypes_df[:25]
archetype_size = archetype_size[["AnnualConsumptionProfile", "ArchetypeSize"]]

eligibility_size = ofgem_archetypes_scheme_eligibility()
whd_eligibility_size = (
    eligibility_size[["AnnualConsumptionProfile", "WHDEligibleSize"]]
    .set_index("AnnualConsumptionProfile")
    .astype("Int64")
)

whd_eligibility_df = archetype_size.merge(
    whd_eligibility_size,
    how="left",
    left_on="AnnualConsumptionProfile",
    right_index=True,
)

whd_eligibility_df.loc[0, "ArchetypeSize"] = 0
whd_eligibility_df.loc[0, "WHDEligibleSize"] = 0

whd_eligibility_df["WHDIneligibleSize"] = (
    whd_eligibility_df["ArchetypeSize"] - whd_eligibility_df["WHDEligibleSize"]
)

# %%
# Merge summary dataframe with look up dataframe on original archetype name
whd_eligibility_df = whd_eligibility_df.rename(
    columns={"AnnualConsumptionProfile": "archetype"}
)
scenarios_summary = scenarios_summary.merge(
    whd_eligibility_df, on="archetype", how="left"
)

# %%
# Add column for size based on scheme_eligible
scenarios_summary["size"] = scenarios_summary.apply(
    lambda row: (
        row["WHDEligibleSize"] if row["scheme_eligible"] else row["WHDIneligibleSize"]
    ),
    axis=1,
)

# Drop processing columns
scenarios_summary = scenarios_summary.drop(
    columns=[
        "ArchetypeSize",
        "WHDEligibleSize",
        "WHDIneligibleSize",
    ]
)

# %% [markdown]
#  **Electricity to gas unit cost ratios**

# %%
# Calculate electricity-to-gas cost ratios for each scenario
scenario_ratios = [
    elec_tariffs[scenario_name].calculate_variable_consumption(1)
    / gas_tariffs[scenario_name].calculate_variable_consumption(1)
    for scenario_name in scenario_weights.keys()
]

cost_ratio_frame = pd.DataFrame(
    {
        "Scenario": scenario_weights.keys(),
        "Electricity to gas unit cost ratio": scenario_ratios,
    }
).reset_index(drop=True)

# %% [markdown]
#  **Total cost to gas, electricity and general taxation for each scenario**

# %%
revenue_streams_df = pd.DataFrame()

for scenario_name in scenario_weights.keys():
    if scenario_name == "Baseline":
        scenario_row = calculate_cost_stream(scenario_name, scenario_weights, levies)
        revenue_streams_df = pd.concat([revenue_streams_df, scenario_row])
    else:
        scenario_row = calculate_cost_stream(
            scenario_name, scenario_weights, uplifted_whd_levies
        )
        revenue_streams_df = pd.concat([revenue_streams_df, scenario_row])

revenue_streams_df = revenue_streams_df.reset_index(drop=True)

# %% [markdown]
# **Levy rates for each scenario**

# %%
levy_rates_df = pd.DataFrame()

for scenario_name in scenario_weights.keys():
    for levy in scenario_levies[scenario_name]:
        row = pd.DataFrame(
            [
                {
                    "Scenario": scenario_name,
                    "Levy name": levy.short_name,
                    "Electricity standing charge": levy.electricity_fixed_rate,
                    "Electricity unit cost": levy.electricity_variable_rate,
                    "Gas standing charge": levy.gas_fixed_rate,
                    "Gas unit cost": levy.gas_variable_rate,
                    "Revenue proportion from electricity": levy.electricity_weight,
                    "Revenue proportion from gas": levy.gas_weight,
                    "Revenue proportion from tax": levy.tax_weight,
                    "Total revenue": levy.revenue,
                }
            ]
        )
        levy_rates_df = pd.concat([levy_rates_df, row])

# %% [markdown]
#  **Saving all output dataframes to Excel workbook**

# %%
# Get today's date
today = datetime.now()

# Format today's date (e.g., YYYY-MM-DD)
date_str = today.strftime("%Y%m%d")

# Define the filename with today's date
filename = f"{PROJECT_DIR}/outputs/data/roundtable_scenarios_data_{date_str}.xlsx"

# %%
# Create an Excel writer object
with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
    # Write each DataFrame to a different sheet
    scenarios_summary.to_excel(writer, sheet_name="Scenarios summary", index=False)
    cost_ratio_frame.to_excel(writer, sheet_name="Scenario cost ratios", index=False)
    revenue_streams_df.to_excel(
        writer, sheet_name="Scenario revenue streams", index=False
    )
    revenue_streams_df.to_excel(
        writer, sheet_name="Scenario revenue streams", index=False
    )
    levy_rates_df.to_excel(writer, sheet_name="Scenario levy rates", index=False)
    ofgem_archetypes_df.to_excel(
        writer, sheet_name="Underlying headline data", index=False
    )
