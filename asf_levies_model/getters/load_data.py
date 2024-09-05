import datetime
import numpy as np
import pandas as pd
import pandera as pa
import re
import warnings
import zipfile

from os import listdir
from requests.sessions import Session
from requests import RequestException
from typing import List

from asf_levies_model import PROJECT_DIR

# Functions for getting and processing Annex 4 data


def download_annex_4(url: str) -> None:
    """Retrieves file from Ofgem website and saves to file."""
    with Session() as session:
        try:
            response = session.get(url)
            date = datetime.datetime.now().strftime("%Y%m%d")
            data_root = f"{PROJECT_DIR}/inputs/data/raw/"
            with open(f"{data_root}{date}_ofgem_annex_4.xlsx", mode="wb") as file:
                file.write(response.content)
            print("File retrieved successfully.")
        except RequestException as rex:
            print("Failed to download annex 4", rex)


def _find_latest_annex(data_root: str, annex_to_find: int) -> str:
    """Gets most recent stored annex date."""
    available_dates = [
        f.split("_")[0]
        for f in listdir(data_root)
        if f"ofgem_annex_{annex_to_find}" in f
    ]
    if len(available_dates) > 0:
        return sorted(available_dates, reverse=True)[0]
    else:
        raise FileNotFoundError(f"No local copies of Annex {annex_to_find} available.")


def _get_excel_sheet_names(file_path: str) -> list:
    """Gets xlsx sheet names quickly."""
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        xml = zip_ref.read("xl/workbook.xml").decode("utf-8")
    sheets = []
    for s_tag in re.findall("<sheet [^>]*", xml):
        sheets.append(re.search('name="[^"]*', s_tag).group(0)[6:])
    return sheets


def _get_raw_dataframe_annex4(policy_name: str) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 4
    spreadsheet tab corresponding to policy of interest."""
    date = datetime.datetime.now()
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    latest_annex_4 = _find_latest_annex(data_root, 4)
    if (
        day_diff := (date - datetime.datetime.strptime(latest_annex_4, "%Y%m%d")).days
    ) > 7:
        warnings.warn(f"Using copy of Annex 4 downloaded {day_diff} days ago.")
    filepath = f"{data_root}{latest_annex_4}_ofgem_annex_4.xlsx"
    try:
        sheet = [
            sheet_name
            for sheet_name in _get_excel_sheet_names(filepath)
            if policy_name in sheet_name
        ][0]
    except:
        raise ValueError("Acronym given does not correspond to a valid policy.")

    return pd.read_excel(
        filepath, sheet_name=sheet, skiprows=4, header=1, index_col=0, engine="calamine"
    ).reset_index(drop=True)


def _get_update_dates(policy_df: pd.DataFrame) -> list:
    """Populates a list containing the month-year dates when data was updated."""
    return (
        policy_df.loc[
            (policy_df == "Updated calculated as of:").sum(axis=1).idxmax(), :
        ]
        .dropna()
        .to_list()[1:]
    )


def _get_charging_years(policy_df: pd.DataFrame, policy_acronym: str) -> list:
    """Populates a list containing the charging/scheme years."""
    policy_string = {
        "ro": "RO charging year:",
        "whd": "WHD scheme year:",
        "eco": "ECO scheme year:",
        "aahedc": "AAHEDC charging year:",
        "ggl": "GGL scheme year:",
    }.get(policy_acronym.lower())
    if not policy_string:
        raise ValueError("Acronym given does not match a valid policy.")
    return (
        policy_df.loc[(policy_df == policy_string).sum(axis=1).idxmax(), :]
        .dropna()
        .to_list()[1:]
    )


def _check_updates_years(update_dates: list, charging_years: list):
    """Checks if number of dates of update and number of charging years are equal."""
    if len(update_dates) == len(charging_years):
        pass
        # print(f"Number of entries: {len(update_dates)}")
    else:
        raise ValueError("Number of time periods do not match!")


def _extract_policy_data(
    parameters: list,
    policy_df: pd.DataFrame,
    update_dates: list,
) -> np.array:
    """Populates a list with specified parameter values from raw dataframe for a given policy."""
    parameter_row_indices = (
        policy_df.isin(parameters)
        .sum(axis=1)
        .astype(bool)
        .pipe(lambda df: df.index[df])
    )

    parameter_cols = (
        policy_df.isin(update_dates)
        .sum(axis=0)
        .astype(bool)
        .pipe(lambda df: df.index[df])
    )

    return policy_df.loc[parameter_row_indices, parameter_cols].to_numpy()


def _process_data(
    policy_acronym: str, policy_parameters: list, column_names: list
) -> pd.DataFrame:
    """Generic function for returning processed annex 4 data."""
    # Create dataframe of raw RO data from spreadsheet tab
    df = _get_raw_dataframe_annex4(policy_acronym)
    # Create list of update dates
    update_dates = _get_update_dates(df)
    # Create list of charging years
    charging_years = _get_charging_years(df, policy_acronym)
    # Check update dates and charging years match
    _check_updates_years(update_dates, charging_years)
    policy_data = _extract_policy_data(policy_parameters, df, update_dates)
    data_tidy_df = pd.concat(
        [
            pd.Series(update_dates, name="UpdateDate"),
            pd.Series(charging_years, name="SchemeYear"),
        ]
        + [
            pd.Series(policy_data[i], name=parameter)
            for i, parameter in enumerate(column_names)
        ],
        axis=1,
    )
    # Make UpdateDate a datetime
    data_tidy_df["UpdateDate"] = pd.to_datetime(
        data_tidy_df["UpdateDate"], format="%B %Y"
    )
    return data_tidy_df


def process_data_RO() -> pd.DataFrame:
    """Extracts and transforms data from corresponding RO tab in annex 4 into tidy format."""
    parameters = [
        "Obligation level for scheme year",
        "Final buy-out price for scheme year",
        "Final buy-out price for previous scheme year",
        "Forecast of annual RPI for previous calendar year",
    ]
    names = [
        "ObligationLevel",
        "BuyOutPriceSchemeYear",
        "BuyOutPricePreviousYear",
        "ForecastAnnualRPIPreviousYear",
    ]
    return _process_data("RO", parameters, names)


def process_data_WHD() -> pd.DataFrame:
    """Extracts and transforms data from corresponding WHD tab in annex 4 into tidy format."""
    parameters = [
        "Target spending for scheme year",
        "   Of which core",
        "   Of which Non-core",
        "Number of customer of obligated suppliers at 31 December of the previous calendar year",
        "Compulsory suppliers % of core group",
    ]
    names = [
        "TargetSpendingForSchemeYear",
        "CoreSpending",
        "NoncoreSpending",
        "ObligatedSuppliersCustomerBase",
        "CompulsorySupplierFractionOfCoreGroup",
    ]
    return _process_data("WHD", parameters, names)


def process_data_AAHEDC() -> pd.DataFrame:
    """Extracts and transforms data from corresponding AAHEDC tab in annex 4 into tidy format."""
    parameters = [
        "Final AAHEDC tariff for current charging year",
        "Final AAHEDC tariff for previous charging year",
        "Forecast of annual RPI for previous charging year",
    ]
    names = ["TariffCurrentYear", "TariffPreviousYear", "ForecastAnnualRPIPreviousYear"]
    return _process_data("AAHEDC", parameters, names)


def process_data_GGL() -> pd.DataFrame:
    """Extracts and transforms data from corresponding GGL tab in annex 4 into tidy format."""
    parameters = ["Levy rate", "Backdated levy rate for first scheme year"]
    names = ["LevyRate", "BackdatedLevyRate"]
    return _process_data("GGL", parameters, names)


def process_data_ECO() -> pd.DataFrame:
    """Extracts and transforms data from corresponding ECO tab in annex 4 into tidy format."""
    parameters = [
        "Annualised costs for scheme year attributed to gas - ECO4",
        "Annualised costs for scheme year attributed to electricity - ECO4",
        "Annualised costs for scheme year attributed to gas - Great British Insulation Scheme (GBIS) - formally ECO+",
        "Annualised costs for scheme year attributed to electricity -  Great British Insulation Scheme (GBIS) - formally ECO+",
        "Uprate to current year prices using GDP deflator",
        "Share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - gas",
        "Share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - electricity",
        "Supply volumes of obligated suppliers - gas",
        "Supply volumes of obligated suppliers - electricity ",
    ]
    names = [
        "AnnualisedCostECO4Gas",
        "AnnualisedCostECO4Electricity",
        "AnnualisedCostGBISGas",
        "AnnualisedCostGBISElectricity",
        "GDPDeflatorToCurrentPricesECO4",
        "GDPDeflatorToCurrentPricesGBIS",
        "FullyObligatedShareOfObligatedSupplierSupplyGas",
        "FullyObligatedShareOfObligatedSupplierSupplyElectricity",
        "ObligatedSupplierVolumeGas",
        "ObligatedSupplierVolumeElectricity",
    ]

    eco_df = _process_data("ECO", parameters, names)

    # Manually fix apparent typo if present in data.
    if (eco_df["UpdateDate"] == "2022-02-01").sum() == 2:
        index = eco_df.index[eco_df["UpdateDate"] == "2022-02-01"][1]
        eco_df.loc[index, "UpdateDate"] = datetime.datetime(year=2023, month=2, day=1)
        eco_df.loc[index, "SchemeYear"] = "2023/2024"

    return eco_df


def validate_input_data(policy_data_tidy_df: pd.DataFrame, policy_data_schema: dict):
    """Perform validation checks on each column of a dataframe with policy-specific data schema."""

    schema = pa.DataFrameSchema(policy_data_schema, coerce=True)

    try:
        schema.validate(policy_data_tidy_df, lazy=True)
        print("All column types are validated.")
    except pa.errors.SchemaErrors as exc:
        print(exc)


def _get_charging_periods(policy_df: pd.DataFrame) -> List[np.array]:
    """Populates a list of lists containing the 28AD charge restriction periods
    (specific to 3i New FIT methodology tab in annex 4)."""
    row_indices = (
        (policy_df == "28AD charge restriction period:")
        .sum(axis=1)
        .astype(bool)
        .pipe(lambda df: df.index[df])[-2:]
    )
    periods = policy_df.loc[row_indices].dropna(axis=1, how="all").to_numpy()
    return [periods[0][1:], periods[1][1:]]


def _get_lookup_periods(policy_df: pd.DataFrame) -> np.array:
    """Populates a list containing lookup periods
    (specific to Table 5 in 3i New FIT methodology tab in annex 4)."""
    lookup_period_row_index = (
        (policy_df == "lookup Period")
        .sum(axis=1)
        .astype(bool)
        .pipe(lambda df: df.index[df])
    )
    return policy_df.loc[lookup_period_row_index].dropna(axis=1).to_numpy()[0][1:]


def _check_periods(charge_period_1: list, charge_period_2: list, lookup_period: list):
    """Checks if number of charge periods and lookup periods are equal."""
    if len(charge_period_1) == len(charge_period_2) == len(lookup_period):
        # print(f"Number of entries: {len(charge_period_1)}")
        return True
    else:
        return False


def _extract_FIT_policy_data(
    parameter_names: str,
    policy_df: pd.DataFrame,
    lookup_periods: list,
) -> np.array:
    """Populates a list with specified parameter values from raw dataframe for the FIT policy."""
    parameter_row_index = (
        policy_df.isin(parameter_names)
        .sum(axis=1)
        .astype(bool)
        .pipe(lambda df: df.index[df])[-4:]
    )

    parameter_col_index = (
        policy_df.loc[min(parameter_row_index) - 1]
        .isin(lookup_periods)
        .pipe(lambda df: df.index[df])
    )
    return policy_df.loc[parameter_row_index, parameter_col_index].to_numpy()


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
    if not _check_periods(charge_periods_1, charge_periods_2, lookup_periods):
        raise ValueError("Number of time periods do not match!")
    # Create a list for each parameter of interest
    parameter_names = [
        "Inflated Levelisation fund (£)",
        "Total Electricity supplied (MWh)",
        "Exempt supply for renewable electricity from outside the UK (MWh)",
        "Exempt supply for EII\n(MWh)",
        "Exempt supply for EII\r\n(MWh)",
    ]
    FIT_parameters = _extract_FIT_policy_data(parameter_names, FIT_df, lookup_periods)
    column_names = [
        "InflatedLevelisationFund",
        "TotalElectricitySupplied",
        "ExemptSupplyOutsideUK",
        "ExemptSupplyEII",
    ]
    # Create dataframe containing FIT data in tidy format
    data_tidy_df = pd.concat(
        [
            pd.Series(charge_periods_1, name="ChargeRestrictionPeriod1"),
            pd.Series(charge_periods_2, name="ChargeRestrictionPeriod2"),
            pd.Series(lookup_periods, name="LookupPeriod"),
        ]
        + [
            pd.Series(FIT_parameters[i], name=parameter)
            for i, parameter in enumerate(column_names)
        ],
        axis=1,
    )
    data_tidy_df["ChargeRestrictionPeriod2_start"] = pd.to_datetime(
        data_tidy_df["ChargeRestrictionPeriod2"].str.split("\s?-\s?", expand=True)[0],
        format="%B %Y",
    )
    data_tidy_df["ChargeRestrictionPeriod2_end"] = pd.to_datetime(
        data_tidy_df["ChargeRestrictionPeriod2"].str.split("\s?-\s?", expand=True)[1],
        format="%B %Y",
    )
    return data_tidy_df


# Functions for getting and processing Annex 9 data


def download_annex_9(url: str) -> None:
    """Retrieves file from Ofgem website and saves to file."""
    with Session() as session:
        try:
            response = session.get(url)
            date = datetime.datetime.now().strftime("%Y%m%d")
            data_root = f"{PROJECT_DIR}/inputs/data/raw/"
            with open(f"{data_root}{date}_ofgem_annex_9.xlsx", mode="wb") as file:
                file.write(response.content)
            print("File retrieved successfully.")
        except RequestException as rex:
            print("Failed to download annex 9", rex)


def _get_raw_dataframe_annex9(data_name: str) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 9
    spreadsheet tab corresponding to policy of interest."""
    date = datetime.datetime.now()
    data_root = f"{PROJECT_DIR}/inputs/data/raw/"
    latest_annex_9 = _find_latest_annex(data_root, 9)
    if (
        day_diff := (date - datetime.datetime.strptime(latest_annex_9, "%Y%m%d")).days
    ) > 7:
        warnings.warn(f"Using copy of Annex 9 downloaded {day_diff} days ago.")
    filepath = f"{data_root}{latest_annex_9}_ofgem_annex_9.xlsx"
    try:
        sheet = [
            sheet_name
            for sheet_name in _get_excel_sheet_names(filepath)
            if data_name in sheet_name
        ][0]
    except:
        raise ValueError("Input does not correspond to a valid tab in the spreadsheet.")

    return pd.read_excel(
        filepath, sheet_name=sheet, header=1, index_col=0, engine="calamine"
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
) -> pd.DataFrame:
    """Generates a dataframe for a single tariff components table (i.e. only one of Electricity single-rate/Electricity multi-register/Gas/Duel Fuel)

    Parameters
    ----------
    input_df : pd.DataFrame
        Dataframe of tariff components tables of interest (output of _slice_tariff_components function)
    type_of_consumption : str
        _"Nil consumption" or "Typical consumption" ONLY.
    table_number : int
        1: Electricity single-rate; 2: Electricity multi-register; 3: Gas; 4: Duel fuel

    Returns
    -------
    pd.DataFrame
        Dataframe of single tariff components table of interest.
    """
    col_names = (
        (input_df == type_of_consumption)
        .sum(axis=0)
        .astype(bool)
        .pipe(lambda df: df.index[df])
    )

    single_tariff_table_df = input_df.loc[
        :,
        col_names[table_number - 1] : (
            input_df.columns[(input_df.columns == col_names[table_number]).argmax() - 1]
            if table_number < len(col_names)
            else None
        ),
    ]

    # Drop empty columns
    single_tariff_table_df = single_tariff_table_df.dropna(axis=1, how="all")
    # Make first row the header column
    single_tariff_table_df.columns = single_tariff_table_df.iloc[0].to_list()
    # Table without first row
    single_tariff_table_df = single_tariff_table_df.iloc[1:, :]
    # Replace "-" with na
    single_tariff_table_df = single_tariff_table_df.replace(
        "[\u002D\u058A\u05BE\u1400\u1806\u2010-\u2015\u2E17\u2E1A\u2E3A\u2E3B\u2E40\u301C\u3030\u30A0\uFE31\uFE32\uFE58\uFE63\uFF0D]",
        None,
        regex=True,
    )
    return single_tariff_table_df


def tidy_tariff_table(input_df: pd.DataFrame, type_of_consumption: str) -> pd.DataFrame:
    """Generates a dataframe for tariff components for one fuel type-payment method in tidy format.

    Parameters
    ----------
    input_df : pd.DataFrame
        Dataframe of tariff components table of interest (output of _extract_single_tariff_table function).
    type_of_consumption : str
        "Nil consumption" or "Typical consumption" ONLY.

    Returns
    -------
    pd.DataFrame
        Dataframing containing tariff component values for one fuel type-payment method in tidy format.
    """
    # Tidy input data
    tidy_df = input_df.melt(
        id_vars=type_of_consumption, var_name="28AD_Charge_Restriction_Period"
    )
    # Add start and end dates
    tidy_df["28AD_Charge_Restriction_Period_start"] = pd.to_datetime(
        tidy_df["28AD_Charge_Restriction_Period"].str.split("-", expand=True)[0]
    )
    tidy_df["28AD_Charge_Restriction_Period_end"] = pd.to_datetime(
        tidy_df["28AD_Charge_Restriction_Period"].str.split("-", expand=True)[1]
    )

    return tidy_df


def ofgem_archetypes_data() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data."""
    dataframe = pd.concat(
        [
            pd.Series(
                [
                    "Typical",
                    "A1",
                    "A2",
                    "A3",
                    "B4",
                    "B5",
                    "B6",
                    "C7",
                    "C8",
                    "C9",
                    "D10",
                    "D11",
                    "D12",
                    "E13",
                    "E14",
                    "F15",
                    "F16",
                    "G17",
                    "G18",
                    "H19",
                    "H20",
                    "I21",
                    "I22",
                    "J23",
                    "J24",
                ],
                name="AnnualConsumptionProfile",
            ),
            pd.Series(
                [
                    2700.0,
                    2742.0,
                    2849.0,
                    3519.0,
                    4811.0,
                    6597.0,
                    3028.0,
                    3649.0,
                    5587.0,
                    3337.0,
                    3881.0,
                    2482.0,
                    3952.0,
                    5075.0,
                    4070.0,
                    6883.0,
                    4317.0,
                    5901.0,
                    5294.0,
                    4907.0,
                    3143.0,
                    4070.0,
                    4684.0,
                    4532.0,
                    7523.0,
                ],
                name="ElectricitySingleRatekWh",
            ),
            pd.Series(
                [
                    11500.0,
                    10933.0,
                    9464.0,
                    10622.0,
                    0.0,
                    0.0,
                    10525.0,
                    13119.0,
                    0.0,
                    13685.0,
                    13981.0,
                    8782.0,
                    16065.0,
                    16722.0,
                    14606.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    11677.0,
                    15461.0,
                    18530.0,
                    16330.0,
                    0.0,
                ],
                name="GaskWh",
            ),
            pd.Series(
                [
                    None,
                    15643,
                    17327,
                    18195,
                    18776,
                    22423,
                    24869,
                    29257,
                    32240,
                    32344,
                    31819,
                    40980,
                    38927,
                    38351,
                    43026,
                    46005,
                    50721,
                    44586,
                    49265,
                    52621,
                    58924,
                    59668,
                    68332,
                    74795,
                    78813,
                ],
                name="GrossAnnualHouseholdIncome",
            ),
            pd.Series(
                [
                    "Typical",
                    "Oldest and poorest",
                    "Low-income older people in social housing",
                    "Low-income adults with disability in social housing",
                    "Old poor people with electric heating",
                    "Pensioners with medical  equipment and/or electric heating",
                    "Low-income couples/singles in small rented/social housing",
                    "Council housing with children",
                    "Electric council housing with 1 child",
                    "Pensioners in semi-detached houses",
                    "Disabled owner-occupiers",
                    "Flats with good EPC",
                    "Pensioners in mansions",
                    "Families with disabilities",
                    "Average families",
                    "Mid income large families on other fuel",
                    "Electric yuppies",
                    "Welsh barns",
                    "Other fuels",
                    "Oil rural older couples",
                    "High income without children",
                    "High income families with 1 child",
                    "Own detached houses with no children",
                    "High income families with 2+ children",
                    "Big rich rural homes with children",
                ],
                name="ArchetypeNickname",
            ),
            pd.Series(
                [
                    1_000_000,
                    578_333,
                    868_191,
                    883_413,
                    731_318,
                    465_288,
                    920_172,
                    659_595,
                    228_477,
                    3_408_514,
                    1_163_946,
                    1_197_075,
                    1_457_829,
                    690_892,
                    1_178_684,
                    323_433,
                    989_639,
                    163_166,
                    667_836,
                    675_712,
                    3_540_270,
                    2_210_494,
                    1_792_593,
                    1_956_103,
                    231_658,
                ],
                name="ArchetypeSize",
            ),
            pd.Series(
                [
                    "Gas",  # Typical
                    "Gas",  # A1
                    "Gas",  # A2
                    "Gas",  # A3
                    "Electricity",  # B4
                    "Electricity/Other",  # B5
                    "Gas",  # B6
                    "Gas",  # C7
                    "Electricity",  # C8
                    "Gas",  # C9
                    "Gas",  # D10
                    "Gas",  # D11
                    "Gas",  # D12
                    "Gas",  # E13
                    "Gas",  # E14
                    "Electricity/Other",  # F15
                    "Electricity",  # F16
                    "Other",  # G17
                    "Other",  # G18
                    "Other",  # H19
                    "Gas",  # H20
                    "Gas",  # I21
                    "Gas",  # I22
                    "Gas",  # J23
                    "Other",  # J24
                ],
                name="ArchetypeHeatingFuel",
            ),
        ],
        axis=1,
    )
    return dataframe
