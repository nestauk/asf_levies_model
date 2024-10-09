import pandas as pd
from typing import Dict, Optional


def _sum_levies(val: float, summary: str, fuel: str, levies: list) -> float:
    """Calculate sum of levies.

    Parameters
    ----------
    val : float
        Gas or electricity consumption value.
    summary : str
        Charging basis, can be 'fixed' or 'variable'.
    fuel : str
        Fuel type, can be 'gas' or 'electricity'.
    levies : list
        Collection of levies used to estimate policy costs.
    Returns
    -------
    float
        Policy cost component value for charging basis and fuel type given.
    """
    if val == 0:
        return 0.0
    else:
        method = {
            "fixed": "calculate_fixed_levy",
            "variable": "calculate_variable_levy",
        }.get(summary)
        args = (
            {
                "fixed": {"gas": (False, True), "electricity": (True, False)},
                "variable": {"gas": (0, val), "electricity": (val, 0)},
            }
            .get(summary)
            .get(fuel)
        )
        return sum([getattr(levy, method)(*args) for levy in levies])


def _calculate_policy_costs(
    levies: list,
    consumption_values_df: pd.DataFrame,
    consumption_profile_column: str,
    electricity_column: str,
    gas_column: str,
    summaries: list,
    scenario: Optional[str] = None,
    consumption_scale_factor: float = 1,
) -> pd.DataFrame:
    """Generates dataframe containing policy costs for a given scenario.

    Parameters
    ----------
    levies : list
        Collection of levies used to estimate policy costs.
    consumption_values_df : pd.DataFrame
        Dataframe of energy use profiles.
    consumption_profile_column : str
        Consumption profile column name in consumption_values_df.
    electricity_column : str
        Electricity consumption column name in consumption_values_df.
    gas_column : str
        Gas consumption column name in consumption_values_df.
    summaries : list
        Summaries required, can be one or more of: 'fixed', 'variable', and 'total'.
    scenario : Optional[str]
        Name of scenario, ignored if None, but appended to output if given.
    consumption_scale_factor : float
        Scaling factor necessary to convert values in consumption_values_df to MWh.

    Returns
    -------
    pd.DataFrame
        A tidy dataframe with a breakdown of policy costs for consumption values.
    """
    if not all([summary in ["fixed", "variable", "total"] for summary in summaries]):
        raise ValueError(
            "summaries can only be one or more of 'fixed', 'variable', 'total'."
        )

    # copy df and scale consumption values
    df = consumption_values_df.copy(deep=True)
    df[gas_column] = df[gas_column] / consumption_scale_factor
    df[electricity_column] = df[electricity_column] / consumption_scale_factor

    summary_cols = []
    for summary in set(summaries).intersection(set(["fixed", "variable"])):
        for col in [electricity_column, gas_column]:
            fuel = "gas" if col == gas_column else "electricity"
            summary_cols.append(
                df[col]
                .apply(lambda x: _sum_levies(x, summary, fuel, levies))
                .rename(f"{fuel} {summary} levy costs")
            )

    if "total" in summaries:
        summary_cols.append(
            df[[gas_column, electricity_column]]
            .apply(
                lambda x: (
                    sum(
                        [
                            levy.calculate_levy(
                                x[electricity_column], x[gas_column], True, True
                            )
                            for levy in levies
                        ]
                    )
                    if x[gas_column] != 0
                    else sum(
                        [
                            levy.calculate_levy(
                                x[electricity_column], x[gas_column], True, False
                            )
                            for levy in levies
                        ]
                    )
                ),
                axis=1,
            )
            .rename("total levy costs")
        )

    consumption_values_df = pd.concat(
        [consumption_values_df] + summary_cols, axis=1
    ).melt(id_vars=consumption_profile_column)

    if scenario:
        consumption_values_df = consumption_values_df.assign(scenario=scenario)

    return consumption_values_df


def _rebalance_levies(
    levies: list, rebalancing_weights: dict, levy_denominators: dict, scenario_name: str
) -> list:
    """Generates a list of rebalanced levies according to provided weights and denominators.

    Parameters
    ----------
    levies : list
        Collection of levies to be rebalanced.
    rebalancing_weights : dict
        A dictionary of scenario dictionaries containing weights that describe the rebalancing required.
    levy_denominators : dict
        A dictionary of denominators for reapportioning revenue subject to rebalancing.
    scenario_name : str
        Name of rebalancing scenario.

    Returns
    -------
    list
        A list of rebalanced levies.
    """
    rebalanced_levies = [
        levy.rebalance_levy(
            **rebalancing_weights.get(scenario_name).get(levy.short_name),
            **levy_denominators[levy.short_name],
        )
        for levy in levies
    ]
    return rebalanced_levies


def process_rebalancing_scenarios(
    levies: list,
    rebalancing_weights: Dict[str, Dict[str, Dict[str, float]]],
    levy_denominators: Dict[str, Dict[str, float]],
    consumption_values_df: pd.DataFrame,
    consumption_profile_column: str,
    electricity_column: str,
    gas_column: str,
    summaries: list,
    consumption_scale_factor: float = 1,
    include_baseline: bool = True,
) -> pd.DataFrame:
    """Generates a tidy dataframe of rebalanced levy costs according to provided scenario weights and denominators.

    If include_baseline is True, the costs given by the originally provided levies are also included as a baseline.

    This function accepts multiple scenarios (rebalancing_weights) in dictionary format: \
{'scenario_name': {'levy short name': {'new_electricity_weight': ...}, ...}, ...}, \
required arguments for rebalancing are:
        new_electricity_weight: float, [0, 1] - share of levy revenue charged to electricity bills.
        new_gas_weight: float, [0, 1] - share of levy revenue charged to gas bills.
        new_tax_weight: float, [0, 1] - share of levy revenue taken out and charged to general taxation.
        new_variable_weight_elec: float, [0, 1] - share of electricity portion of levy revenue charged variably by consumption.
        new_fixed_weight_elec: float, [0, 1] - share of electricity portion of levy revenue fixed and charged by customer/meter.
        new_variable_weight_gas: float, [0, 1] - share of gas portion of levy revenue charged variably by consumption.
        new_fixed_weight_gas: float, [0, 1] - share of gas portion of levy revenue fixed and charged by customer/meter.

    Established levy short names are: ro, aahedc, eco, fit, ggl, whd.

    This function only accept one set of levy denominators, we assume the denominators hold for all scenarios. Denominators \
are specific to each levy in the dictionary format: {'levy_short_name': {'supply_elec': ...}, ...}, required denominator \
arguments are:
        supply_elec: float, [0, inf) Amount of electricity supplied (MWh).
        supply_gas: float, [0, inf) Amount of gas supplied (MWh).
        customers_elec: int, [0, inf) Number of electricity customers (count of customers/meters).
        customers_gas: int, [0, inf) Number of gas customers (count of customers/meters).

    Finally, the function accepts a dataframe `consumption_values_df` in which each row is a consumption profile, \
    with a profile name (e.g. 'typical'), an electricity consumption (e.g. 2.7 MWh), and a gas consumption (e.g. 11.5MWh). \
    If the consumptions are not given in MWh a `consumption_scale_factor` can be included to scale the given values to MWh.

    Parameters
    ----------
    levies : list
        Collection of levies to be rebalanced.
    rebalancing_weights : dict
        A dictionary of scenario names, each mapping a dictionary of weights that describe the rebalancing required in that scenario. \
It is assumed that the rebalancing weights are the same for each levy.
    levy_denominators : dict
        A dictionary of denominators for reapportioning revenue subject to rebalancing. These are assumed to be common across all scenarios.
    consumption_values_df : pd.DataFrame
        Dataframe of energy use profiles.
    consumption_profile_column : str
        Consumption profile column name in consumption_values_df.
    electricity_column : str
        Electricity consumption column name in consumption_values_df.
    gas_column : str
        Gas consumption column name in consumption_values_df.
    summaries : list
        Summaries required, can be one or more of: 'fixed', 'variable', and 'total'.
    consumption_scale_factor : float
        Scaling factor necessary to convert values in consumption_values_df to MWh.
    include_baseline : bool (default: True)
        Whether to include the input `levies` as 'baseline' data in the output.

    Returns
    -------
    pd.DataFrame
        A tidy dataframe with a breakdown of policy costs for consumption values by scenario.
    """
    if include_baseline:
        baseline = _calculate_policy_costs(
            levies,
            consumption_values_df,
            consumption_profile_column,
            electricity_column,
            gas_column,
            summaries,
            "Baseline",
            consumption_scale_factor,
        )

    scenarios = []
    for scenario in rebalancing_weights.keys():
        new_levies = _rebalance_levies(
            levies, rebalancing_weights, levy_denominators, scenario
        )
        scenarios.append(
            _calculate_policy_costs(
                new_levies,
                consumption_values_df,
                consumption_profile_column,
                electricity_column,
                gas_column,
                summaries,
                scenario,
                consumption_scale_factor,
            )
        )

    return pd.concat([baseline] + scenarios, ignore_index=True)


def process_rebalancing_scenario_bills(
    elec_bills: Dict,
    gas_bills: Dict,
    levies: list,
    rebalancing_weights: Dict[str, dict],
    levy_denominators: Dict[str, dict],
    consumption_values_df: pd.DataFrame,
    consumption_profile_column: str,
    electricity_column: str,
    gas_column: str,
    consumption_scale_factor: float = 1,
    include_baseline: bool = True,
) -> pd.DataFrame:
    """Calculate energy bill for given scenarios under levy rebalancing.

    If include_baseline is True, the bill costs given by the originally provided levies are also included as a baseline.

    elec_bills, gas_bills must include scenarios named in rebalancing_weights.

    elec_bills and gas_bills are dictionaries of scenario name : tariff object pairs, for instance: \
{'scenario_name': GasStandardCredit, ...}, a baseline can be computed by including a 'baseline' key with a tariff object.

    This function accepts multiple scenarios (rebalancing_weights) in dictionary format: \
{'scenario_name': {'levy short name': {'new_electricity_weight': ...}, ...}, ...}, \
required arguments for rebalancing are:
        new_electricity_weight: float, [0, 1] - share of levy revenue charged to electricity bills.
        new_gas_weight: float, [0, 1] - share of levy revenue charged to gas bills.
        new_tax_weight: float, [0, 1] - share of levy revenue taken out and charged to general taxation.
        new_variable_weight_elec: float, [0, 1] - share of electricity portion of levy revenue charged variably by consumption.
        new_fixed_weight_elec: float, [0, 1] - share of electricity portion of levy revenue fixed and charged by customer/meter.
        new_variable_weight_gas: float, [0, 1] - share of gas portion of levy revenue charged variably by consumption.
        new_fixed_weight_gas: float, [0, 1] - share of gas portion of levy revenue fixed and charged by customer/meter.

    Established levy short names are: ro, aahedc, eco, fit, ggl, whd.

    This function only accept one set of levy denominators, we assume the denominators hold for all scenarios. Denominators \
are specific to each levy in the dictionary format: {'levy_short_name': {'supply_elec': ...}, ...}, required denominator \
arguments are:
        supply_elec: float, [0, inf) Amount of electricity supplied (MWh).
        supply_gas: float, [0, inf) Amount of gas supplied (MWh).
        customers_elec: int, [0, inf) Number of electricity customers (count of customers/meters).
        customers_gas: int, [0, inf) Number of gas customers (count of customers/meters).

    Finally, the function accepts a dataframe `consumption_values_df` in which each row is a consumption profile, \
    with a profile name (e.g. 'typical'), an electricity consumption (e.g. 2.7 MWh), and a gas consumption (e.g. 11.5MWh). \
    If the consumptions are not given in MWh a `consumption_scale_factor` can be included to scale the given values to MWh.

    Parameters
    ----------
    elec_bills: Dict
        Dictionary of scenario name : electricity tariff object pairs.
    gas_bills: Dict
        Dictionary of scenario name : gas tariff object pairs.
    levies : list
        Collection of levies to be rebalanced.
    rebalancing_weights : dict
        A dictionary of scenario names, each mapping a dictionary of weights that describe the rebalancing required in that scenario. \
It is assumed that the rebalancing weights are the same for each levy.
    levy_denominators : dict
        A dictionary of denominators for reapportioning revenue subject to rebalancing. These are assumed to be common across all scenarios.
    consumption_values_df : pd.DataFrame
        Dataframe of energy use profiles.
    consumption_profile_column : str
        Consumption profile column name in consumption_values_df.
    electricity_column : str
        Electricity consumption column name in consumption_values_df.
    gas_column : str
        Gas consumption column name in consumption_values_df.
    consumption_scale_factor : float
        Scaling factor necessary to convert values in consumption_values_df to MWh.
    include_baseline : bool (default: True)
        Whether to include the input `levies` as 'baseline' data in the output.

    Returns
    -------
    pd.DataFrame
        A tidy dataframe with a breakdown of bill costs for consumption values by scenario.

    """

    if include_baseline:
        summary_bill_costs_baseline = consumption_values_df.loc[
            :,
            [consumption_profile_column],
        ]

        summary_bill_costs_baseline["electricity bill incl VAT"] = elec_bills.get(
            "baseline"
        ).calculate_total_consumption(
            consumption_values_df[electricity_column] / consumption_scale_factor,
            vat=True,
        )

        summary_bill_costs_baseline["gas bill incl VAT"] = gas_bills.get(
            "baseline"
        ).calculate_total_consumption(
            consumption_values_df[gas_column] / consumption_scale_factor, vat=True
        )

        summary_bill_costs_baseline["total bill incl VAT"] = (
            summary_bill_costs_baseline["electricity bill incl VAT"]
            + summary_bill_costs_baseline["gas bill incl VAT"]
        )

        summary_bill_costs_baseline["scenario"] = "Baseline"

    summary_bill_costs_scenarios = {}
    for scenario in rebalancing_weights.keys():
        new_levies = _rebalance_levies(
            levies, rebalancing_weights, levy_denominators, scenario
        )
        # Update the bill policy costs in line with scenario
        elec_bills.get(scenario).pc_nil = sum(
            [levy.calculate_fixed_levy(True, False) for levy in new_levies]
        )
        elec_bills.get(scenario).pc = sum(
            [levy.calculate_variable_levy(1, 0) for levy in new_levies]
        )
        gas_bills.get(scenario).pc_nil = sum(
            [levy.calculate_fixed_levy(False, True) for levy in new_levies]
        )
        gas_bills.get(scenario).pc = sum(
            [levy.calculate_variable_levy(0, 1) for levy in new_levies]
        )

        summary_bill_costs_scenario = consumption_values_df.loc[
            :,
            [
                consumption_profile_column,
            ],
        ]
        summary_bill_costs_scenario["electricity bill incl VAT"] = elec_bills.get(
            scenario
        ).calculate_total_consumption(
            consumption_values_df[electricity_column] / consumption_scale_factor,
            vat=True,
        )
        summary_bill_costs_scenario["gas bill incl VAT"] = gas_bills.get(
            scenario
        ).calculate_total_consumption(
            consumption_values_df[gas_column] / consumption_scale_factor,
            vat=True,
        )

        summary_bill_costs_scenario["total bill incl VAT"] = (
            summary_bill_costs_scenario["electricity bill incl VAT"]
            + summary_bill_costs_scenario["gas bill incl VAT"]
        )

        summary_bill_costs_scenario["scenario"] = scenario

        summary_bill_costs_scenarios[scenario] = summary_bill_costs_scenario

    if include_baseline:
        summary_bill_costs = pd.concat([summary_bill_costs_baseline])

        for name in summary_bill_costs_scenarios.keys():
            summary_bill_costs = pd.concat(
                [summary_bill_costs, summary_bill_costs_scenarios[name]]
            )
    else:
        summary_bill_costs = pd.concat(
            [
                summary_bill_costs_scenarios[name]
                for name in summary_bill_costs_scenarios.keys()
            ]
        )

    summary_bill_costs = summary_bill_costs.melt(
        id_vars=[consumption_profile_column, "scenario"]
    )

    return summary_bill_costs


def transform_income_decile_eligibility(
    decile_dataframe: pd.DataFrame, eligible_deciles: float
) -> pd.DataFrame:
    """Collapses columns of dataframes from ofgem_archetypes_equivalised_income_deciles() or ofgem_archetypes_net_income_deciles() to one column describing the total number of households in the eligible income deciles provided.

    Parameters
    ----------
    decile_dataframe : pd.DataFrame
        Dataframe from data loading functions ofgem_archetypes_equivalised_income_deciles() or ofgem_archetypes_net_income_deciles().
    eligible_deciles : float
        Desired number of eligible income deciles, e.g. 4 corresponds to the lowest 4 income deciles.

    """
    income_eligibility = decile_dataframe[
        ["AnnualConsumptionProfile", "ArchetypeSize"]
    ].copy(deep=True)

    income_eligibility["Eligible income deciles"] = eligible_deciles

    if eligible_deciles == 1:
        income_eligibility["IncomeDecilesEligibilitySize"] = decile_dataframe.iloc[:, 2]

    else:
        income_eligibility["IncomeDecilesEligibilitySize"] = decile_dataframe.iloc[
            :, 2 : eligible_deciles + 2
        ].sum(axis=1)

    return income_eligibility


def subsidisation_table(
    scenario_outputs: pd.DataFrame,
    scenario_name: str,
    rebate: float,
    eligibility_criteria: str,
    eligibility_dataframe: pd.DataFrame,
    eligible_deciles: int = 0,
    ineligible_households_pay: bool = True,
) -> pd.DataFrame:
    """Processes rebalancing scenario results to add a rebate for targeted vulnerable households.

    Parameters
    ----------
    scenario_outputs : pd.DataFrame
       Concatenated output dataframes from process_rebalancing_scenarios() and process_rebalancing_scenario_bills().
    scenario_name : str
        Name of scenario of interest, must match a scenario name present in scenario_outputs.
    rebate : float
        Amount to discount from eligible households' bills.
    eligibility_criteria : str
        Criteria description, currently only accepts the following: ['Cold Weather Payments','ECO', 'Warm Homes Discount', 'Winter Fuel Payments', 'Retired Economic Status', 'Pension Guarantee Credit', 'Pension Savings Credit', 'Income Deciles'].
        Else, a KeyError is raised.
    eligibility_dataframe : pd.DataFrame
        Dataframe with a column of archetype names (column header "AnnualConsumptionProfile") and remaining columns listing the number of eligible households for a given criteria. Pre-processed dataframes include the outputs
        from ofgem_archetypes_scheme_eligibility(), ofgem_archetypes_retired_pension() and transform_income_decile_eligibility(ofgem_archetypes_XX_income_deciles, eligible_deciles).
    eligible_deciles : int, optional
        Number of deciles qualify for eligibility criteria if based on income, e.g. 4 corresponds to the 4 lowest income deciles; by default 0.
    ineligible_households_pay : bool, optional
        Whether rebate fund should be equally distributed among ineligible household bills, by default True.

    """

    # Create new dataframe
    bills = scenario_outputs[
        (scenario_outputs["variable"] == "total bill incl VAT")
        | (scenario_outputs["variable"] == "ArchetypeSize")
    ]
    bills = bills[bills["scenario"] == scenario_name]
    bills = bills[bills.AnnualConsumptionProfile != "Typical"].reset_index(drop=True)
    bills = bills.pivot_table(
        index=[
            "AnnualConsumptionProfile",
            "scenario",
        ],
        columns="variable",
        values="value",
    ).reset_index()
    bills = bills.rename(columns={"total bill incl VAT": "ScenarioBaseBill"})

    # Add column for Current bills
    baseline_bills = scenario_outputs[
        (scenario_outputs["variable"] == "total bill incl VAT")
        & (scenario_outputs["scenario"] == "Baseline")
    ]
    baseline_bills = baseline_bills[
        baseline_bills.AnnualConsumptionProfile != "Typical"
    ].reset_index()
    bills.insert(3, "CurrentBaselineBill", baseline_bills["value"])

    # Look up for eligibility criteria and column names
    eligibility_dict = {
        "Cold Weather Payments": "CWPEligibleSize",  # ofgem_archetypes_scheme_elibility()
        "ECO": "ECOEligibleSize",  # ofgem_archetypes_scheme_elibility()
        "Warm Homes Discount": "WHDEligibleSize",  # ofgem_archetypes_scheme_elibility()
        "Winter Fuel Payments": "WFPEligibleSize",  # ofgem_archetypes_scheme_elibility()
        "Retired Economic Status": "RetiredEconomicStatusSize",  # ofgem_archetypes_retired_pension()
        "Pension Guarantee Credit": "PensionGuaranteeCreditRecipients",  # ofgem_archetypes_retired_pension()
        "Pension Savings Credit": "PensionGuaranteeCreditRecipients",  # ofgem_archetypes_retired_pension()
        "Income Deciles": "IncomeDecilesEligibilitySize",  # transform_income_decile_eligibility()
    }

    if eligibility_criteria not in eligibility_dict.keys():
        raise KeyError(
            f"Please provide criteria type from the following: {list(eligibility_dict.keys())}"
        )

    # If eligibility criteria not based on income deciles
    if eligible_deciles == 0:
        bills["EligibilityCriteria"] = eligibility_criteria

    # If eligibility criteria is based on income deciles
    else:
        bills["EligibilityCriteria"] = (
            str(eligible_deciles) + " Lowest " + eligibility_criteria
        )

    def find_eligible_size(row, eligibility_criteria):
        return eligibility_dataframe.loc[
            eligibility_dataframe["AnnualConsumptionProfile"] == row,
            eligibility_criteria,
        ].values[0]

    # Add column for number of eligible households
    bills["NumberOfEligibleHouseholds"] = bills["AnnualConsumptionProfile"].apply(
        find_eligible_size, args=(eligibility_dict.get(eligibility_criteria),)
    )

    # Add column for total funds needed to provide rebate for eligible households in archetype
    bills["TotalRequiredRebateAmount"] = rebate * bills["NumberOfEligibleHouseholds"]

    # Add columns for new bill and bill change with respect to current bills for eligible households
    bills["EligibleHouseholdBill"] = bills["ScenarioBaseBill"] - rebate
    bills["EligibleHouseholdBillChangeFromCurrentBill"] = (
        bills["EligibleHouseholdBill"] - bills["CurrentBaselineBill"]
    )

    # Add column for number of ineligible households
    bills["NumberOfIneligibleHouseholds"] = (
        bills["ArchetypeSize"] - bills["NumberOfEligibleHouseholds"]
    )
    rebate_fund = rebate * bills["NumberOfEligibleHouseholds"].sum()

    # Add columns for new bill and bill change with respect to current bills for ineligible households
    # If rebate mechanism does or does not involve ineligible households covering the costs
    if ineligible_households_pay:
        rebate_payment = rebate_fund / bills["NumberOfIneligibleHouseholds"].sum()
        bills["IneligibleHouseholdBill"] = bills["ScenarioBaseBill"] + rebate_payment
    else:
        bills["IneligibleHouseholdBill"] = bills["ScenarioBaseBill"]

    bills["IneligibleHouseholdBillChangeFromCurrentBill"] = (
        bills["IneligibleHouseholdBill"] - bills["CurrentBaselineBill"]
    )

    return bills
