import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa
from typing import List

from asf_levies_model import PROJECT_DIR

# Functions for getting and processing Annex 4 data


def download_annex_4(url: str):
    """Retrieves file from Ofgem website and saves to file."""

    response = requests.get(url)
    if response.ok == True and response.status_code == 200:
        date = datetime.datetime.now().strftime("%Y%m%d")
        data_root = f"{PROJECT_DIR}/inputs/data/raw/"
        with open(f"{data_root}{date}_ofgem_annex_4.xlsx", mode="wb") as file:
            print("File retrieved successfully.")
            file.write(response.content)


def _get_raw_dataframe_annex4(policy_name: str) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 4 spreadsheet tab corresponding to policy of interest."""
    date = datetime.datetime.now().strftime("%Y%m%d")
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    xls = pd.ExcelFile(f"{data_root}{date}_ofgem_annex_4.xlsx")

    try:
        sheet = [
            sheet_name for sheet_name in xls.sheet_names if policy_name in sheet_name
        ][0]
    except:
        raise ValueError("Acronym given does not correspond to a valid policy.")

    skip_rows = list(range(0, 4))
    return pd.read_excel(
        f"{data_root}{date}_ofgem_annex_4.xlsx",
        sheet_name=sheet,
        skiprows=lambda x: x in skip_rows,
        header=1,
        index_col=0,
    ).reset_index(drop=True)


def _get_update_dates(policy_df: pd.DataFrame) -> list:
    """Populates a list containing the month-year dates when data was updated."""
    update_date_row_index = np.where(policy_df == "Updated calculated as of:")[0][0]
    update_dates = policy_df.loc[update_date_row_index, :].values.flatten().tolist()
    update_dates = [
        x for x in update_dates if not (isinstance(x, float) and math.isnan(x))
    ]
    del update_dates[0]
    return update_dates


def _get_charging_years(policy_df: pd.DataFrame, policy_acronym: str) -> list:
    """Populates a list containing the charging/scheme years."""

    if "ro" in policy_acronym.lower():
        charging_year_row_index = np.where(policy_df == "RO charging year:")[0][0]
        charging_years = (
            policy_df.loc[charging_year_row_index, :].values.flatten().tolist()
        )
        charging_years = [
            x for x in charging_years if not (isinstance(x, float) and math.isnan(x))
        ]
        del charging_years[0]

    elif "whd" in policy_acronym.lower():
        charging_year_row_index = np.where(policy_df == "WHD scheme year:")[0][0]
        charging_years = (
            policy_df.loc[charging_year_row_index, :].values.flatten().tolist()
        )
        charging_years = [
            x for x in charging_years if not (isinstance(x, float) and math.isnan(x))
        ]
        del charging_years[0]

    elif "eco" in policy_acronym.lower():
        charging_year_row_index = np.where(policy_df == "ECO scheme year:")[0][0]
        charging_years = (
            policy_df.loc[charging_year_row_index, :].values.flatten().tolist()
        )
        charging_years = [
            x for x in charging_years if not (isinstance(x, float) and math.isnan(x))
        ]
        del charging_years[0]

    elif "aahedc" in policy_acronym.lower():
        charging_year_row_index = np.where(policy_df == "AAHEDC charging year:")[0][0]
        charging_years = (
            policy_df.loc[charging_year_row_index, :].values.flatten().tolist()
        )
        charging_years = [
            x for x in charging_years if not (isinstance(x, float) and math.isnan(x))
        ]
        del charging_years[0]

    elif "ggl" in policy_acronym.lower():
        charging_year_row_index = np.where(policy_df == "GGL scheme year:")[0][0]
        charging_years = (
            policy_df.loc[charging_year_row_index, :].values.flatten().tolist()
        )
        charging_years = [
            x for x in charging_years if not (isinstance(x, float) and math.isnan(x))
        ]
        del charging_years[0]

    else:
        raise ValueError("Acronym given does not match a valid policy.")

    return charging_years


def _check_updates_years(update_dates: list, charging_years: list):
    """Checks if number of dates of update and number of charging years are equal."""
    if len(update_dates) == len(charging_years):
        print(f"Number of entries: {len(update_dates)}")
    else:
        raise ValueError("Number of time periods do not match!")


def _extract_policy_data(
    parameter_name: str,
    policy_df: pd.DataFrame,
    charging_years: list,
    update_dates: list,
) -> list:
    """Populates a list with specified parameter values from raw dataframe for a given policy."""
    parameter_row_index = np.where(policy_df == parameter_name)[0][0]

    parameter_values_list = []
    for i in range(0, len(charging_years)):
        update_col_index = np.where((policy_df == update_dates[i]))[1]
        year_col_index = np.where((policy_df == charging_years[i]))[1]
        parameter_col_index = [i for i in year_col_index if i == update_col_index][0]
        parameter_value = policy_df.iloc[parameter_row_index, parameter_col_index]
        parameter_values_list.append(parameter_value)

    return parameter_values_list


def process_data_RO() -> pd.DataFrame:
    """Extracts and transforms data from corresponding RO tab in annex 4 into tidy format."""

    # Create dataframe of raw RO data from spreadsheet tab
    RO_df = _get_raw_dataframe_annex4("RO")

    # Create list of update dates
    RO_update_dates = _get_update_dates(RO_df)

    # Create list of charging years
    RO_charging_years = _get_charging_years(RO_df, "RO")

    # Check update dates and charging years match
    _check_updates_years(RO_update_dates, RO_charging_years)

    # Create a list for each parameter of interest
    parameter_names = [
        "Obligation level for scheme year",
        "Final buy-out price for scheme year",
        "Final buy-out price for previous scheme year",
        "Forecast of annual RPI for previous calendar year",
    ]
    RO_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_policy_data(
            parameter, RO_df, RO_charging_years, RO_update_dates
        )
        RO_parameters.append(parameter_values)

    # Create dataframe containing RO data in tidy format
    RO_data_dict = {
        "UpdateDate": pd.Series(RO_update_dates),
        "SchemeYear": pd.Series(RO_charging_years),
        "ObligationLevel": pd.Series(RO_parameters[0]),
        "BuyOutPriceSchemeYear": pd.Series(RO_parameters[1]),
        "BuyOutPricePreviousYear": pd.Series(RO_parameters[2]),
        "ForecastAnnualRPIPreviousYear": pd.Series(RO_parameters[3]),
    }
    RO_data_tidy_df = pd.DataFrame(RO_data_dict)

    return RO_data_tidy_df


def process_data_WHD() -> pd.DataFrame:
    """Extracts and transforms data from corresponding WHD tab in annex 4 into tidy format."""

    # Create dataframe of raw WHF data from spreadsheet tab
    WHD_df = _get_raw_dataframe_annex4("WHD")

    # Create list of update dates
    WHD_update_dates = _get_update_dates(WHD_df)

    # Create list of charging years
    WHD_charging_years = _get_charging_years(WHD_df, "WHD")

    # Check update dates and charging years match
    _check_updates_years(WHD_update_dates, WHD_charging_years)

    # Create a list for each parameter of interest
    parameter_names = [
        "Target spending for scheme year",
        "   Of which core",
        "   Of which Non-core",
        "Number of customer of obligated suppliers at 31 December of the previous calendar year",
        "Compulsory suppliers % of core group",
    ]

    WHD_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_policy_data(
            parameter, WHD_df, WHD_charging_years, WHD_update_dates
        )
        WHD_parameters.append(parameter_values)

    # Create dataframe containing WHD data in tidy format
    WHD_data_dict = {
        "UpdateDate": pd.Series(WHD_update_dates),
        "SchemeYear": pd.Series(WHD_charging_years),
        "TargetSpendingForSchemeYear": pd.Series(WHD_parameters[0]),
        "CoreSpending": pd.Series(WHD_parameters[1]),
        "NoncoreSpending": pd.Series(WHD_parameters[2]),
        "ObligatedSuppliersCustomerBase": pd.Series(WHD_parameters[3]),
        "CompulsorySupplierFractionOfCoreGroup": pd.Series(WHD_parameters[4]),
    }
    WHD_data_tidy_df = pd.DataFrame(WHD_data_dict)

    return WHD_data_tidy_df


def process_data_ECO() -> pd.DataFrame:
    """Extracts and transforms data from corresponding ECO tab in annex 4 into tidy format."""

    # Create dataframe of raw ECO data from spreadsheet tab
    ECO_df = _get_raw_dataframe_annex4("ECO")

    # Fix typo - second occurrence of February 2022 (Cell AB10)
    row_index_to_correct = np.where(ECO_df == "February 2022")[0][1]
    col_index_to_correct = np.where(ECO_df == "February 2022")[1][1]
    ECO_df.iloc[row_index_to_correct, col_index_to_correct] = "February 2023"

    # Differentiate between GDP deflator rows - ECO4
    row_index_to_edit_ECO4 = np.where(
        ECO_df == "Uprate to current year prices using GDP deflator"
    )[0][0]
    col_index_to_edit_ECO4 = np.where(
        ECO_df == "Uprate to current year prices using GDP deflator"
    )[1][0]
    ECO_df.iloc[row_index_to_edit_ECO4, col_index_to_edit_ECO4] = (
        "Uprate to current year prices using GDP deflator - ECO4"
    )
    row_index_to_edit_GBIS = np.where(
        ECO_df == "Uprate to current year prices using GDP deflator"
    )[0][0]
    col_index_to_edit_GBIS = np.where(
        ECO_df == "Uprate to current year prices using GDP deflator"
    )[1][0]
    ECO_df.iloc[row_index_to_edit_GBIS, col_index_to_edit_GBIS] = (
        "Uprate to current year prices using GDP deflator - GBIS"
    )

    # Create list of update dates
    ECO_update_dates = _get_update_dates(ECO_df)

    # Create list of charging years
    ECO_charging_years = _get_charging_years(ECO_df, "ECO")

    # Check update dates and charging years match
    _check_updates_years(ECO_update_dates, ECO_charging_years)

    # Create a list for each parameter of interest
    parameter_names = [
        "Annualised costs for scheme year attributed to gas - ECO4",
        "Annualised costs for scheme year attributed to electricity - ECO4",
        "Annualised costs for scheme year attributed to gas - Great British Insulation Scheme (GBIS) - formally ECO+",
        "Annualised costs for scheme year attributed to electricity -  Great British Insulation Scheme (GBIS) - formally ECO+",
        "Uprate to current year prices using GDP deflator - ECO4",
        "Uprate to current year prices using GDP deflator - GBIS",
        "Share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - gas",
        "Share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - electricity",
        "Supply volumes of obligated suppliers - gas",
        "Supply volumes of obligated suppliers - electricity ",
    ]
    ECO_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_policy_data(
            parameter, ECO_df, ECO_charging_years, ECO_update_dates
        )
        ECO_parameters.append(parameter_values)

    # Create dataframe containing ECO data in tidy format
    ECO_data_dict = {
        "UpdateDate": pd.Series(ECO_update_dates),
        "SchemeYear": pd.Series(ECO_charging_years),
        "AnnualisedCostECO4Gas": pd.Series(ECO_parameters[0]),
        "AnnualisedCostECO4Electricity": pd.Series(ECO_parameters[1]),
        "AnnualisedCostGBISGas": pd.Series(ECO_parameters[2]),
        "AnnualisedCostGBISElectricity": pd.Series(ECO_parameters[3]),
        "GDPDeflatorToCurrentPricesECO4": pd.Series(ECO_parameters[4]),
        "GDPDeflatorToCurrentPricesGBIS": pd.Series(ECO_parameters[5]),
        "FullyObligatedShareOfObligatedSupplierSupplyGas": pd.Series(ECO_parameters[6]),
        "FullyObligatedShareOfObligatedSupplierSupplyElectricity": pd.Series(
            ECO_parameters[7]
        ),
        "ObligatedSupplierVolumeGas": pd.Series(ECO_parameters[8]),
        "ObligatedSupplierVolumeElectricity": pd.Series(ECO_parameters[9]),
    }

    ECO_data_tidy_df = pd.DataFrame(ECO_data_dict)

    return ECO_data_tidy_df


def process_data_AAHEDC() -> pd.DataFrame:
    """Extracts and transforms data from corresponding AAHEDC tab in annex 4 into tidy format."""

    # Create dataframe of raw AAHEDC data from spreadsheet tab
    AAHEDC_df = _get_raw_dataframe_annex4("AAHEDC")

    # Create list of update dates
    AAHEDC_update_dates = _get_update_dates(AAHEDC_df)

    # Create list of charging years
    AAHEDC_charging_years = _get_charging_years(AAHEDC_df, "AAHEDC")

    # Check update dates and charging years match
    _check_updates_years(AAHEDC_update_dates, AAHEDC_charging_years)

    # Create a list for each parameter of interest
    parameter_names = [
        "Final AAHEDC tariff for current charging year",
        "Final AAHEDC tariff for previous charging year",
        "Forecast of annual RPI for previous charging year",
    ]
    AAHEDC_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_policy_data(
            parameter, AAHEDC_df, AAHEDC_charging_years, AAHEDC_update_dates
        )
        AAHEDC_parameters.append(parameter_values)

    # Create dataframe containing AAHEDC data in tidy format
    AAHEDC_data_dict = {
        "UpdateDate": pd.Series(AAHEDC_update_dates),
        "SchemeYear": pd.Series(AAHEDC_charging_years),
        "TariffCurrentYear": pd.Series(AAHEDC_parameters[0]),
        "TariffPreviousYear": pd.Series(AAHEDC_parameters[1]),
        "ForecastAnnualRPIPreviousYear": pd.Series(AAHEDC_parameters[2]),
    }

    AAHEDC_data_tidy_df = pd.DataFrame(AAHEDC_data_dict)

    return AAHEDC_data_tidy_df


def process_data_GGL() -> pd.DataFrame:
    """Extracts and transforms data from corresponding GGL tab in annex 4 into tidy format."""

    # Create dataframe of raw GGL data from spreadsheet tab
    GGL_df = _get_raw_dataframe_annex4("GGL")

    # Create list of update dates
    GGL_update_dates = _get_update_dates(GGL_df)

    # Create list of charging years
    GGL_charging_years = _get_charging_years(GGL_df, "GGL")

    # Check update dates and charging years match
    _check_updates_years(GGL_update_dates, GGL_charging_years)

    # Create a list for each parameter of interest
    parameter_names = ["Levy rate", "Backdated levy rate for first scheme year"]
    GGL_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_policy_data(
            parameter, GGL_df, GGL_charging_years, GGL_update_dates
        )
        GGL_parameters.append(parameter_values)

    # Create dataframe containing GGL data in tidy format
    GGL_data_dict = {
        "UpdateDate": pd.Series(GGL_update_dates),
        "SchemeYear": pd.Series(GGL_charging_years),
        "LevyRate": pd.Series(GGL_parameters[0]),
        "BackdatedLevyRate": pd.Series(GGL_parameters[1]),
    }

    GGL_data_tidy_df = pd.DataFrame(GGL_data_dict)

    return GGL_data_tidy_df


def validate_input_data(policy_data_tidy_df: pd.DataFrame, policy_data_schema: dict):
    """Perform validation checks on each column of a dataframe with policy-specific data schema."""

    schema = pa.DataFrameSchema(policy_data_schema, coerce=True)

    try:
        schema.validate(policy_data_tidy_df, lazy=True)
        print("All column types are validated.")
    except pa.errors.SchemaErrors as exc:
        print(exc)


def _get_charging_periods(policy_df: pd.DataFrame) -> List[list]:
    """Populates a list of lists containing the 28AD charge restriction periods (specific to 3i New FIT methodology tab in annex 4)."""
    charge_periods = []
    for x in [-2, -1]:
        charge_period_row_index = np.where(
            policy_df == "28AD charge restriction period:"
        )[0][x]
        charge_period = (
            policy_df.loc[charge_period_row_index, :].values.flatten().tolist()
        )
        charge_period = [
            x for x in charge_period if not (isinstance(x, float) and math.isnan(x))
        ]
        del charge_period[0]
        charge_periods.append(charge_period)

    if len(charge_periods[0]) != len(charge_periods[1]):
        raise ValueError("Number of charge restriction periods don't match!")
    else:
        pass

    return charge_periods


def _get_lookup_periods(policy_df: pd.DataFrame) -> list:
    """Populates a list containing lookup periods (specific to Table 5 in 3i New FIT methodology tab in annex 4)."""
    lookup_period_row_index = np.where(policy_df == "lookup Period")[0]
    lookup_periods = policy_df.loc[lookup_period_row_index, :].values[0].tolist()
    lookup_periods = [
        x for x in lookup_periods if not (isinstance(x, float) and math.isnan(x))
    ]
    del lookup_periods[0]
    return lookup_periods


def _check_periods(charge_period_1: list, charge_period_2: list, lookup_period: list):
    """Checks if number of charge periods and lookup periods are equal."""
    if len(charge_period_1) == len(charge_period_2) == len(lookup_period):
        print(f"Number of entries: {len(charge_period_1)}")
    else:
        raise ValueError("Number of time periods do not match!")


def _extract_FIT_policy_data(
    parameter_name: str,
    policy_df: pd.DataFrame,
    charge_periods: list,
    lookup_periods: list,
) -> list:
    """Populates a list with specified parameter values from raw dataframe for the FIT policy."""

    parameter_row_index = np.where(policy_df == parameter_name)[0][-1]

    parameter_values_list = []
    for i in range(0, len(lookup_periods)):
        charge_col_index = np.where((policy_df == charge_periods[i]))[1][-1]  # unique
        lookup_col_index = np.where((policy_df == lookup_periods[i]))[1]  # duplicates

        lookup_col_index = [i for i in lookup_col_index if i == charge_col_index][0]

        if charge_col_index == lookup_col_index:
            parameter_col_index = charge_col_index
        else:
            raise ValueError(
                "Unable to find a match between charge restriction and lookup periods."
            )

        parameter_value = policy_df.iloc[parameter_row_index, parameter_col_index]
        parameter_values_list.append(parameter_value)

    return parameter_values_list


def process_data_FIT() -> pd.DataFrame:
    """Extracts and transforms data from corresponding New FIT tab in annex 4 into tidy format."""

    # Create dataframe of raw FIT data from spreadsheet tab
    FIT_df = _get_raw_dataframe_annex4("New FIT")

    # Create list of 28AD charge restriction periods (Table 5)
    charge_periods = _get_charging_periods(FIT_df)
    charge_periods_1 = charge_periods[0]
    charge_periods_2 = charge_periods[1]

    # Create list of lookup periods (Table 5)
    lookup_periods = _get_lookup_periods(FIT_df)

    # Check charge restriction periods and lookup periods match
    _check_periods(charge_periods_1, charge_periods_2, lookup_periods)

    # Create a list for each parameter of interest
    parameter_names = [
        "Inflated Levelisation fund (£)",
        "Total Electricity supplied (MWh)",
        "Exempt supply for renewable electricity from outside the UK (MWh)",
        "Exempt supply for EII\n(MWh)",
    ]

    FIT_parameters = []
    for parameter in parameter_names:
        parameter_values = _extract_FIT_policy_data(
            parameter, FIT_df, charge_periods_2, lookup_periods
        )
        FIT_parameters.append(parameter_values)

    # Create dataframe containing FIT data in tidy format
    FIT_data_dict = {
        "ChargeRestrictionPeriod1": pd.Series(charge_periods_1),
        "ChargeRestrictionPeriod2": pd.Series(charge_periods_2),
        "LookupPeriod": pd.Series(lookup_periods),
        "InflatedLevelisationFund": pd.Series(FIT_parameters[0]),
        "TotalElectricitySupplied": pd.Series(FIT_parameters[1]),
        "ExemptSupplyOutsideUK": pd.Series(FIT_parameters[2]),
        "ExemptSupplyEII": pd.Series(FIT_parameters[3]),
    }
    FIT_data_tidy_df = pd.DataFrame(FIT_data_dict)

    return FIT_data_tidy_df


# Functions for getting and processing Annex 9 data


def download_annex_9(url: str):
    """Retrieves file from Ofgem website and saves to file."""

    response = requests.get(url)
    if response.ok == True and response.status_code == 200:
        date = datetime.datetime.now().strftime("%Y%m%d")
        data_root = f"{PROJECT_DIR}/inputs/data/raw/"
        with open(f"{data_root}{date}_ofgem_annex_9.xlsx", mode="wb") as file:
            print("File retrieved successfully.")
            file.write(response.content)


def _get_raw_dataframe_annex9(data_name: str) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 9 spreadsheet tab corresponding to data of interest."""
    date = datetime.datetime.now().strftime("%Y%m%d")
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    xls = pd.ExcelFile(f"{data_root}{date}_ofgem_annex_9.xlsx")

    try:
        sheet = [
            sheet_name for sheet_name in xls.sheet_names if data_name in sheet_name
        ][0]
    except:
        raise ValueError(
            "String given does not correspond to a valid tab in the spreadsheet."
        )

    return pd.read_excel(
        f"{data_root}{date}_ofgem_annex_9.xlsx",
        sheet_name=sheet,
        header=1,
        index_col=0,
    ).reset_index(drop=True)


def slice_tariff_components_tables(
    sheet_start_row: int, levelisation: bool
) -> pd.DataFrame:
    """Extracts tariff components tables of interest from Annex 9 tab "1c Consumption adjusted levels".

    Parameters
    ----------
    sheet_start_row : int
        Row number of header row in target tables in sheet "1c Consumption adjusted levels".

    levelisation : bool
        Boolean representing whether "Levelisation" tariff component is included in tariff table of interest.

    Returns
    -------
    pd.DataFrame
        Dataframe of tariff components tables of interest.
    """

    # Create dataframe of raw consumption adjusted level costs from spreadsheet tab
    consumption_adjusted_levels_df = _get_raw_dataframe_annex9(
        "Consumption adjusted levels"
    )

    if levelisation is True:
        tariff_tables_df = consumption_adjusted_levels_df.iloc[
            (sheet_start_row - 3) : (sheet_start_row + 10), :
        ]
    else:
        tariff_tables_df = consumption_adjusted_levels_df.iloc[
            (sheet_start_row - 3) : (sheet_start_row + 9), :
        ]

    return tariff_tables_df


def extract_single_tariff_table(
    input_df: pd.DataFrame,
    type_of_consumption: str,
    table_number: int,
    number_of_time_periods: int,
) -> pd.DataFrame:
    """Generates a dataframe for a single tariff components table (i.e. only one of Electricity single-rate/Electricity multi-register/Gas)

    Parameters
    ----------
    input_df : pd.DataFrame
        Dataframe of tariff components tables of interest (output of _slice_tariff_components function)
    type_of_consumption : str
        _"Nil consumption" or "Typical consumption" ONLY.
    table_number : int
        1: Electricity single-rate; 2: Electricity multi-register; 3: Gas.
    numer_of_time_periods : int
        Number of cells in header row (time periods).

    Returns
    -------
    pd.DataFrame
        Dataframe of single tariff components table of interest.
    """
    start_column = np.where(input_df == type_of_consumption)[1][table_number - 1]

    single_tariff_table_df = input_df.iloc[
        :, start_column : (start_column + number_of_time_periods + 2)
    ]

    return single_tariff_table_df


from typing import List


def _get_parameter_values(
    input_df: pd.DataFrame, type_of_consumption: str, levelisation: bool
) -> List[list]:
    """Generates a list of lists containing values of each tariff component.

    Parameters
    ----------
    input_df : pd.DataFrame
        Dataframe of tariff components table of interest (output of _extract_single_tariff_table function).
    type_of_consumption : str
        "Nil consumption" or "Typical consumption" ONLY.
    levelisation : bool
        Boolean representing whether "Levelisation" tariff component is included in tariff table of interest.

    Returns
    -------
    List[list]
        List of lists with each sub-list containing values of each tariff component.
    """
    parameter_names = [
        type_of_consumption,
        "DF",
        "CM",
        "AA",
        "PC",
        "NC",
        "OC",
        "SMNCC",
        "PAAC",
        "PAP",
        "EBIT",
        "HAP",
        "Levelisation",
    ]
    parameters = []
    if levelisation is True:
        for parameter in parameter_names:
            parameter_row_index = np.where(input_df == parameter)[0]
            parameter_values = (
                input_df.iloc[parameter_row_index, :].values.flatten().tolist()
            )
            parameter_values = [
                x
                for x in parameter_values
                if not (isinstance(x, float) and math.isnan(x))
            ]
            del parameter_values[0]
            parameters.append(parameter_values)
    else:
        for parameter in parameter_names[0:-1]:
            parameter_row_index = np.where(input_df == parameter)[0]
            parameter_values = (
                input_df.iloc[parameter_row_index, :].values.flatten().tolist()
            )
            parameter_values = [
                x
                for x in parameter_values
                if not (isinstance(x, float) and math.isnan(x))
            ]
            del parameter_values[0]
            parameters.append(parameter_values)

    return parameters


def tidy_tariff_table(
    input_df: pd.DataFrame, type_of_consumption: str, levelisation: bool
) -> pd.DataFrame:
    """Generates a dataframe for tariff components for one fuel type-payment method in tidy format.

    Parameters
    ----------
    input_df : pd.DataFrame
        Dataframe of tariff components table of interest (output of _extract_single_tariff_table function).
    type_of_consumption : str
        "Nil consumption" or "Typical consumption" ONLY.
    levelisation : bool
        Boolean representing whether "Levelisation" tariff component is included in tariff table of interest.

    Returns
    -------
    pd.DataFrame
        Dataframing containing tariff component values for one fuel type-payment method in tidy format.
    """

    list_of_parameters = _get_parameter_values(
        input_df, type_of_consumption, levelisation
    )

    if levelisation is True:
        data_dict = {
            "TimePeriod": pd.Series(list_of_parameters[0]),
            "DirectFuel": pd.Series(list_of_parameters[1]),
            "CapacityMarket": pd.Series(list_of_parameters[2]),
            "AdjustmentAllowance": pd.Series(list_of_parameters[3]),
            "PolicyCosts": pd.Series(list_of_parameters[4]),
            "NetworkCosts": pd.Series(list_of_parameters[5]),
            "OperatingCosts": pd.Series(list_of_parameters[6]),
            "SmartMeteringNetCostChange": pd.Series(list_of_parameters[7]),
            "PaymentAdjustmentAdditionalCost": pd.Series(list_of_parameters[8]),
            "PaymentAdjustmentPercentage": pd.Series(list_of_parameters[9]),
            "EarningsBeforeInterestAndTaxes": pd.Series(list_of_parameters[10]),
            "HeadroomAllowancePercentage": pd.Series(list_of_parameters[11]),
            "Levelisation": pd.Series(list_of_parameters[12]),
        }
    else:
        data_dict = {
            "TimePeriod": pd.Series(list_of_parameters[0]),
            "DirectFuel": pd.Series(list_of_parameters[1]),
            "CapacityMarket": pd.Series(list_of_parameters[2]),
            "AdjustmentAllowance": pd.Series(list_of_parameters[3]),
            "PolicyCosts": pd.Series(list_of_parameters[4]),
            "NetworkCosts": pd.Series(list_of_parameters[5]),
            "OperatingCosts": pd.Series(list_of_parameters[6]),
            "SmartMeteringNetCostChange": pd.Series(list_of_parameters[7]),
            "PaymentAdjustmentAdditionalCost": pd.Series(list_of_parameters[8]),
            "PaymentAdjustmentPercentage": pd.Series(list_of_parameters[9]),
            "EarningsBeforeInterestAndTaxes": pd.Series(list_of_parameters[10]),
            "HeadroomAllowancePercentage": pd.Series(list_of_parameters[11]),
        }

    tariff_tidy_df = pd.DataFrame(data_dict)

    # Replace hyphens with zero values
    tariff_tidy_df = tariff_tidy_df.map(lambda x: x if x != "-" else float(0))

    print(f"Number of entries: {len(tariff_tidy_df)}")

    return tariff_tidy_df


def get_typical_consumption_values(
    sheet_start_row: int, sheet_start_col: int
) -> pd.DataFrame:
    """Generates a dataframe containing typical energy consumption values from Annex 9.

    Parameters
    ----------
    sheet_start_row : int
        Row number of first cell in consumption values table in sheet.

    sheet_start_row : int
        Column number of first cell in consumption values table in sheet (i.e. column B -> 2).

    Returns
    -------
    pd.DataFrame
        Dataframe containing typical energy consumption values for electricity and gas.
    """

    # Create dataframe of raw consumption adjusted level costs from spreadsheet tab
    consumption_adjusted_levels_df = _get_raw_dataframe_annex9(
        "Consumption adjusted levels"
    )

    consumption_values_df = consumption_adjusted_levels_df.iloc[
        (sheet_start_row - 3) : (sheet_start_row + 1),
        (sheet_start_col - 2) : (sheet_start_col),
    ]

    # Create list of fuel/metering arrangement consumption values
    parameter_names = [
        "Electricity: Single-rate ",
        "Electricity: Multi-register",
        "Gas",
    ]
    TCV_parameters = []
    for parameter in parameter_names:
        row_index = np.where(consumption_values_df == parameter)[0][0]
        parameter_values = [consumption_values_df.iloc[row_index, 1]]
        # Convert MWh to kWh
        parameter_values = [x * 1000 for x in parameter_values]
        TCV_parameters.append(parameter_values)

    consumption_profile = ["Typical"]

    # Create dataframe containing RO data in tidy format
    TCV_data_dict = {
        "AnnualConsumptionProfile": pd.Series(consumption_profile),
        "ElectricitySingleRatekWh": pd.Series(TCV_parameters[0]),
        "ElectricityMultiRegisterkWh": pd.Series(TCV_parameters[1]),
        "GaskWh": pd.Series(TCV_parameters[2]),
    }
    consumption_values_tidy_df = pd.DataFrame(TCV_data_dict)

    return consumption_values_tidy_df


# Functions for processing Ofgem energy archetypes data


def get_ofgem_archetypes_data():
    """Reads Ofgem energy archetypes data from spreadsheet file and populates a dataframe."""
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    ofgem_archetypes_raw = pd.read_excel(
        f"{data_root}Ofgem_Consumer_Archetypes_2024.xlsx"
    )

    # Extract rows with archetype information only (A1 - J24 archetypes)
    ofgem_archetypes_df = ofgem_archetypes_raw.iloc[0:24, :]

    # Clean
    ofgem_archetypes_df = ofgem_archetypes_df.drop(
        ["Total Gas Consumption", "Total electricity consumption"], axis=1
    )
    ofgem_archetypes_df = ofgem_archetypes_df.replace(np.nan, 0)
    ofgem_archetypes_df = ofgem_archetypes_df.rename(
        columns={
            "Number of Households": "NumberOfHouseholds",
            "Main Heating Fuel": "MainHeatingFuel",
            "Gross Annual Household Income (£)": "GrossAnnualHouseholdIncome£",
            "Average Annual Elec Consumption (kWh)": "AverageAnnualElecConsumptionkWh",
            "Average Annual Gas Consumption (kWh)": "AverageAnnualGasConsumptionkWh",
        }
    )

    print(f"Number of archetypes: {len(ofgem_archetypes_df)}")

    return ofgem_archetypes_df


def combine_consumption_values(
    ofgem_archetypes_df: pd.DataFrame, main_consumption_df: pd.DataFrame
) -> pd.DataFrame:
    """Extracts relevant data for each Ofgem archetype and appends it to main consumption dataframe containing typical values.

    Parameters
    ----------
    archetypes_df : pd.DataFrame
        Dataframe containing Ofgem energy archetypes data (output of get_ofgem_archetypes_data function).
    main_consumption_df : pd.DataFrame
        Dataframe containing typical consumption values from Annex 9 (output of get_typical_consumption_values function).

    Returns
    -------
    pd.DataFrame
        Dataframe containing both typical and archetype consumption values for electricity and gas.
    """
    # Create dataframe to append to main consumption values dataframe
    archetypes = pd.Series(ofgem_archetypes_df.Archetype)
    archetype_average_electricity = pd.Series(
        ofgem_archetypes_df.AverageAnnualElecConsumptionkWh
    )
    archetype_average_gas = pd.Series(
        ofgem_archetypes_df.AverageAnnualGasConsumptionkWh
    )
    multi_register_placeholder = pd.Series([0] * len(ofgem_archetypes_df))

    archetype_consumption_data_dict = {
        "AnnualConsumptionProfile": pd.Series(archetypes),
        "ElectricitySingleRatekWh": pd.Series(archetype_average_electricity),
        "ElectricityMultiRegisterkWh": pd.Series(multi_register_placeholder),
        "GaskWh": pd.Series(archetype_average_gas),
    }

    archetype_consumption_df = pd.DataFrame(archetype_consumption_data_dict)

    # Append to main consumption values dataframe
    combined_consumption_values_df = pd.concat(
        [main_consumption_df, archetype_consumption_df], axis=0
    ).reset_index(drop=True)

    return combined_consumption_values_df


# Functions for processing DUKES data


def download_dukes(url: str, table_number: str):
    """Retrieves file from gov.uk website and saves to file.

    Parameters
    ----------
    url : str
        URL of target file.
    table_number : str
        DUKES table number, separated with underscore instead of period (e.g. 4_1, not 4.1).
    """

    response = requests.get(url)
    if response.ok == True and response.status_code == 200:
        date = datetime.datetime.now().strftime("%Y%m%d")
        data_root = f"{PROJECT_DIR}/inputs/data/raw/"
        with open(f"{data_root}{date}_dukes_{table_number}.xlsx", mode="wb") as file:
            print("File retrieved successfully.")
            file.write(response.content)


def _get_raw_dataframe_dukes(tab_name: str, table_number: str) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from DUKES spreadsheet tab corresponding to table of interest.

    Parameters
    ----------
    tab_name : str
        Name of spreadsheet tab in Excel file.
    table_number : str
        DUKES table number, separated with underscore instead of period (e.g. 4_1, not 4.1).

    Returns
    -------
    pd.DataFrame
        Dataframe of raw data from spreadsheet tab.

    Raises
    ------
    ValueError
        If tab_name given does not correspond to a tab in the spreadsheet.
    """

    date = datetime.datetime.now().strftime("%Y%m%d")
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    xls = pd.ExcelFile(f"{data_root}{date}_dukes_{table_number}.xlsx")

    try:
        sheet = [
            sheet_name for sheet_name in xls.sheet_names if tab_name in sheet_name
        ][0]
    except:
        raise ValueError(
            "Acronym given does not correspond to a valid tab in the spreadsheet."
        )

    skip_rows = list(range(0, 2))
    return pd.read_excel(
        f"{data_root}{date}_dukes_{table_number}.xlsx",
        sheet_name=sheet,
        skiprows=lambda x: x in skip_rows,
        header=1,
    ).reset_index(drop=True)


def get_dukes_supply_data(dukes_year: str) -> tuple:
    """Extracts total and domestic gas and electricity supply values from DUKES 4.1 and 5.2, respectively.

    Parameters
    ----------
    dukes_year : str
        Year of interest for data.

    Returns
    -------
    tuple
        Tuple of floats (Total gas supply, Domestic gas supply, Total electricity supply, Domestic electricity supply).
    """

    ## Gas supply values
    # Dataframe of sheet in tab corresponding to year in DUKES 4.1 (gas)
    dukes_4_1_df = _get_raw_dataframe_dukes(dukes_year, "4_1")

    # Extract values
    total_row = np.where(dukes_4_1_df["Column1"] == "Total supply")
    dukes_total_gas = dukes_4_1_df.iloc[total_row]["Natural gas"].values[0]
    domestic_row = np.where(dukes_4_1_df["Column1"] == "Domestic")
    dukes_domestic_gas = dukes_4_1_df.iloc[domestic_row]["Natural gas"].values[0]

    ## Electricity supply values
    # Dataframe of sheet in tab of interest
    dukes_5_2_df = _get_raw_dataframe_dukes("5.2", "5_2")

    # Extract values
    year_column = np.where(dukes_5_2_df == f"Total ({dukes_year})")[1][0]
    total_row = np.where(dukes_5_2_df == "Total supply")[0][0]
    domestic_row = np.where(dukes_5_2_df == "Domestic [note 6]")[0][0]

    dukes_total_elec = dukes_5_2_df.iloc[total_row, year_column]
    dukes_domestic_elec = dukes_5_2_df.iloc[domestic_row, year_column]

    return dukes_total_gas, dukes_domestic_gas, dukes_total_elec, dukes_domestic_elec


# Functions for processing Subnational Consumption Statistics data


def download_subnational_consumption(url: str, fuel: str):
    """Retrieves file from gov.uk website and saves to file.

    Parameters
    ----------
    url : str
        URL of target file.
    fuel : str
        "gas" or "electricity".
    """

    response = requests.get(url)
    if response.ok == True and response.status_code == 200:
        date = datetime.datetime.now().strftime("%Y%m%d")
        data_root = f"{PROJECT_DIR}/inputs/data/raw/"
        with open(
            f"{data_root}{date}_subnational_consumption_{fuel}.xlsx", mode="wb"
        ) as file:
            print("File retrieved successfully.")
            file.write(response.content)


def _get_raw_dataframe_subnational_consumption(
    tab_name: str, fuel: str
) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from subnational consumption spreadsheet tab corresponding to table of interest.

    Parameters
    ----------
    tab_name : str
        Name of spreadsheet tab in Excel file.
    fuel : str
        "gas" or "electricity".

    Returns
    -------
    pd.DataFrame
       Dataframe of raw data from spreadsheet tab.

    Raises
    ------
    ValueError
        If tab_name given does not correspond to a tab in the spreadsheet.
    """

    date = datetime.datetime.now().strftime("%Y%m%d")
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    xls = pd.ExcelFile(f"{data_root}{date}_subnational_consumption_{fuel}.xlsx")

    try:
        sheet = [
            sheet_name for sheet_name in xls.sheet_names if tab_name in sheet_name
        ][0]
    except:
        raise ValueError(
            "Acronym given does not correspond to a valid tab in the spreadsheet."
        )

    skip_rows = list(range(0, 2))
    return pd.read_excel(
        f"{data_root}{date}_subnational_consumption_{fuel}.xlsx",
        sheet_name=sheet,
        skiprows=lambda x: x in skip_rows,
        header=1,
    ).reset_index(drop=True)


def get_subnational_consumption_data(subnational_year: str) -> tuple:
    """Extracts meter point and consumption data from Subnational Consumption Statistics for gas and electricity.

    Parameters
    ----------
    subnational_year : str
        Year of interest for data.

    Returns
    -------
    tuple
        Tuple of floats (x8) for gas meters (total, domestic), electricity meters (total, domestic), gas consumption (total, domestic) and electricity consumption (total, domestic).
    """

    ## Gas

    # Dataframe of sheet in tab of interest
    subnational_consumption_gas_df = _get_raw_dataframe_subnational_consumption(
        subnational_year, "gas"
    )

    # Extract values - number of meters
    gb_row = np.where(
        subnational_consumption_gas_df == "Great Britain (inc unallocated)"
    )[0][0]
    all_meters_row = np.where(
        subnational_consumption_gas_df == "Number of meters\n(thousands):\nAll meters"
    )[1][0]
    subnational_total_gas_meters = (
        subnational_consumption_gas_df.iloc[gb_row, all_meters_row] * 1000
    )
    domestic_meters_row = np.where(
        subnational_consumption_gas_df == "Number of meters\n(thousands):\nDomestic\n"
    )[1][0]
    subnational_domestic_gas_meters = (
        subnational_consumption_gas_df.iloc[gb_row, domestic_meters_row] * 1000
    )

    # Extract values - consumption
    gb_row = np.where(
        subnational_consumption_gas_df == "Great Britain (inc unallocated)"
    )[0][0]
    total_row = np.where(
        subnational_consumption_gas_df == "Total consumption\n(GWh):\nAll meters"
    )[1][0]
    subnational_total_gas = (
        subnational_consumption_gas_df.iloc[gb_row, total_row] * 1000
    )
    domestic_row = np.where(
        subnational_consumption_gas_df == "Total consumption\n(GWh):\nDomestic\n"
    )[1][0]
    subnational_domestic_gas = (
        subnational_consumption_gas_df.iloc[gb_row, domestic_row] * 1000
    )

    ## Electricity

    # Dataframe of sheet in tab of interest
    subnational_consumption_elec_df = _get_raw_dataframe_subnational_consumption(
        subnational_year, "electricity"
    )

    # Extract values - number of meters
    gb_row = np.where(
        subnational_consumption_elec_df == "Great Britain (inc unallocated)"
    )[0][0]
    all_meters_row = np.where(
        subnational_consumption_elec_df == "Number of meters\n(thousands):\nAll meters"
    )[1][0]
    subnational_total_elec_meters = (
        subnational_consumption_elec_df.iloc[gb_row, all_meters_row] * 1000
    )
    domestic_meters_row = np.where(
        subnational_consumption_elec_df
        == "Number of meters\n(thousands):\nAll Domestic"
    )[1][0]
    subnational_domestic_elec_meters = (
        subnational_consumption_elec_df.iloc[gb_row, domestic_meters_row] * 1000
    )

    # Extract values - consumption
    gb_row = np.where(
        subnational_consumption_elec_df == "Great Britain (inc unallocated)"
    )[0][0]
    total_row = np.where(
        subnational_consumption_elec_df == "Total consumption\n(GWh):\nAll meters"
    )[1][0]
    subnational_total_elec = (
        subnational_consumption_elec_df.iloc[gb_row, total_row] * 1000
    )
    domestic_row = np.where(
        subnational_consumption_elec_df == "Total consumption\n(GWh):\nAll Domestic"
    )[1][0]
    subnational_domestic_elec = (
        subnational_consumption_elec_df.iloc[gb_row, domestic_row] * 1000
    )

    return (
        subnational_total_gas_meters,
        subnational_domestic_gas_meters,
        subnational_total_gas,
        subnational_domestic_gas,
        subnational_total_elec_meters,
        subnational_domestic_elec_meters,
        subnational_total_elec,
        subnational_domestic_elec,
    )
