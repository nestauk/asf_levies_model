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
    rebalancing_weights: Dict[str, dict],
    levy_denominators: Dict[str, dict],
    consumption_values_df: pd.DataFrame,
    consumption_profile_column: str,
    electricity_column: str,
    gas_column: str,
    summaries: list,
    consumption_scale_factor: float = 1,
    include_baseline: bool = True,
) -> pd.DataFrame:
    """Generates a tidy dataframe of rebalanced levy costs according to provided scenario weights and denominators.

    This function accepts multiple scenarios in dictionary format: {'scenario_name': {'new_electricity_weight': ...}, ...}, \
required arguments for rebalancing are:
        new_electricity_weight: float, [0, 1] - share of levy revenue charged to electricity bills.
        new_gas_weight: float, [0, 1] - share of levy revenue charged to gas bills.
        new_tax_weight: float, [0, 1] - share of levy revenue taken out and charged to general taxation.
        new_variable_weight_elec: float, [0, 1] - share of electricity portion of levy revenue charged variably by consumption.
        new_fixed_weight_elec: float, [0, 1] - share of electricity portion of levy revenue fixed and charged by customer/meter.
        new_variable_weight_gas: float, [0, 1] - share of gas portion of levy revenue charged variably by consumption.
        new_fixed_weight_gas: float, [0, 1] - share of gas portion of levy revenue fixed and charged by customer/meter.

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
