import datetime
import numpy as np
import pandas as pd
import pandera as pa
import re
import warnings
import zipfile
import os

from io import BytesIO
from os import listdir
from requests.sessions import Session
from requests import RequestException
from typing import List, Optional, Union, Dict

from asf_levies_model import config, PROJECT_DIR

# Create Ofgem annex data route variable from config
if config.get("data_downloads").get("annex"):
    # If a root has been specified, use it.
    if "PROJECT_DIR" in config.get("data_downloads").get("annex"):
        # If the root uses the PROJECT_DIR, add that back in
        DATA_ROOT = (
            config.get("data_downloads")
            .get("annex")
            .replace("PROJECT_DIR", str(PROJECT_DIR))
        )
    else:
        # Otherwise jsut use the given root.
        DATA_ROOT = config.get("data_downloads").get("annex")
else:
    # If no data_output root has been given, just use the base PROJECT_DIR
    DATA_ROOT = str(PROJECT_DIR) + "/"

# Create archetypes data route variable from config
if config.get("data_downloads").get("archetypes"):
    # If a root has been specified, use it.
    if "PROJECT_DIR" in config.get("data_downloads").get("archetypes"):
        # If the root uses the PROJECT_DIR, add that back in
        ARCHETYPE_DATA_ROOT = (
            config.get("data_downloads")
            .get("archetypes")
            .replace("PROJECT_DIR", str(PROJECT_DIR))
        )
    else:
        # Otherwise just use the given root.
        ARCHETYPE_DATA_ROOT = config.get("data_downloads").get("archetypes")
else:
    # If no data_output root has been given, just use the base PROJECT_DIR
    ARCHETYPE_DATA_ROOT = str(PROJECT_DIR) + "/"

# Create 28AD Charge restriction period index

_outer_idx = pd.IntervalIndex.from_tuples(
    [
        (pd.to_datetime("2015-04-01 00:00:00"), pd.to_datetime("2015-09-30 23:59:59")),
        (pd.to_datetime("2015-10-01 00:00:00"), pd.to_datetime("2016-03-31 23:59:59")),
        (pd.to_datetime("2016-04-01 00:00:00"), pd.to_datetime("2016-09-30 23:59:59")),
        (pd.to_datetime("2016-10-01 00:00:00"), pd.to_datetime("2017-03-31 23:59:59")),
        (pd.to_datetime("2017-04-01 00:00:00"), pd.to_datetime("2017-09-30 23:59:59")),
        (pd.to_datetime("2017-10-01 00:00:00"), pd.to_datetime("2018-03-31 23:59:59")),
        (pd.to_datetime("2018-04-01 00:00:00"), pd.to_datetime("2018-09-30 23:59:59")),
        (pd.to_datetime("2018-10-01 00:00:00"), pd.to_datetime("2019-03-31 23:59:59")),
        (pd.to_datetime("2019-01-01 00:00:00"), pd.to_datetime("2019-03-31 23:59:59")),
        (pd.to_datetime("2019-04-01 00:00:00"), pd.to_datetime("2019-09-30 23:59:59")),
        (pd.to_datetime("2019-10-01 00:00:00"), pd.to_datetime("2020-03-31 23:59:59")),
        (pd.to_datetime("2020-04-01 00:00:00"), pd.to_datetime("2020-09-30 23:59:59")),
        (pd.to_datetime("2020-10-01 00:00:00"), pd.to_datetime("2021-03-31 23:59:59")),
        (pd.to_datetime("2021-04-01 00:00:00"), pd.to_datetime("2021-09-30 23:59:59")),
        (pd.to_datetime("2021-10-01 00:00:00"), pd.to_datetime("2022-03-31 23:59:59")),
        (pd.to_datetime("2022-04-01 00:00:00"), pd.to_datetime("2022-09-30 23:59:59")),
        (pd.to_datetime("2022-10-01 00:00:00"), pd.to_datetime("2023-03-31 23:59:59")),
        (pd.to_datetime("2022-10-01 00:00:00"), pd.to_datetime("2023-03-31 23:59:59")),
        (pd.to_datetime("2023-04-01 00:00:00"), pd.to_datetime("2023-09-30 23:59:59")),
        (pd.to_datetime("2023-04-01 00:00:00"), pd.to_datetime("2023-09-30 23:59:59")),
        (pd.to_datetime("2023-10-01 00:00:00"), pd.to_datetime("2024-03-31 23:59:59")),
        (pd.to_datetime("2023-10-01 00:00:00"), pd.to_datetime("2024-03-31 23:59:59")),
        (pd.to_datetime("2024-04-01 00:00:00"), pd.to_datetime("2024-09-30 23:59:59")),
        (pd.to_datetime("2024-04-01 00:00:00"), pd.to_datetime("2024-09-30 23:59:59")),
        (pd.to_datetime("2024-10-01 00:00:00"), pd.to_datetime("2025-03-31 23:59:59")),
        (pd.to_datetime("2024-10-01 00:00:00"), pd.to_datetime("2025-03-31 23:59:59")),
        (pd.to_datetime("2025-04-01 00:00:00"), pd.to_datetime("2025-09-30 23:59:59")),
        (pd.to_datetime("2025-04-01 00:00:00"), pd.to_datetime("2025-09-30 23:59:59")),
        (pd.to_datetime("2025-10-01 00:00:00"), pd.to_datetime("2026-03-31 23:59:59")),
        (pd.to_datetime("2025-10-01 00:00:00"), pd.to_datetime("2026-03-31 23:59:59")),
        (pd.to_datetime("2026-04-01 00:00:00"), pd.to_datetime("2026-09-30 23:59:59")),
        (pd.to_datetime("2026-04-01 00:00:00"), pd.to_datetime("2026-09-30 23:59:59")),
        (pd.to_datetime("2026-10-01 00:00:00"), pd.to_datetime("2027-03-31 23:59:59")),
        (pd.to_datetime("2026-10-01 00:00:00"), pd.to_datetime("2027-03-31 23:59:59")),
        (pd.to_datetime("2027-04-01 00:00:00"), pd.to_datetime("2027-09-30 23:59:59")),
        (pd.to_datetime("2027-04-01 00:00:00"), pd.to_datetime("2027-09-30 23:59:59")),
        (pd.to_datetime("2027-10-01 00:00:00"), pd.to_datetime("2028-03-31 23:59:59")),
        (pd.to_datetime("2027-10-01 00:00:00"), pd.to_datetime("2028-03-31 23:59:59")),
        (pd.to_datetime("2028-04-01 00:00:00"), pd.to_datetime("2028-09-30 23:59:59")),
        (pd.to_datetime("2028-04-01 00:00:00"), pd.to_datetime("2028-09-30 23:59:59")),
        (pd.to_datetime("2028-10-01 00:00:00"), pd.to_datetime("2029-03-31 23:59:59")),
        (pd.to_datetime("2028-10-01 00:00:00"), pd.to_datetime("2029-03-31 23:59:59")),
        (pd.to_datetime("2029-04-01 00:00:00"), pd.to_datetime("2029-09-30 23:59:59")),
        (pd.to_datetime("2029-04-01 00:00:00"), pd.to_datetime("2029-09-30 23:59:59")),
        (pd.to_datetime("2029-10-01 00:00:00"), pd.to_datetime("2030-03-31 23:59:59")),
        (pd.to_datetime("2029-10-01 00:00:00"), pd.to_datetime("2030-03-31 23:59:59")),
        (pd.to_datetime("2030-04-01 00:00:00"), pd.to_datetime("2030-09-30 23:59:59")),
        (pd.to_datetime("2030-04-01 00:00:00"), pd.to_datetime("2030-09-30 23:59:59")),
        (pd.to_datetime("2030-10-01 00:00:00"), pd.to_datetime("2031-03-31 23:59:59")),
    ],
    closed="both",
    name="28AD Charge Restriction Period 6 Month",
)

_inner_idx = pd.IntervalIndex.from_tuples(
    [
        (pd.to_datetime("2015-04-01 00:00:00"), pd.to_datetime("2015-09-30 23:59:59")),
        (pd.to_datetime("2015-10-01 00:00:00"), pd.to_datetime("2016-03-31 23:59:59")),
        (pd.to_datetime("2016-04-01 00:00:00"), pd.to_datetime("2016-09-30 23:59:59")),
        (pd.to_datetime("2016-10-01 00:00:00"), pd.to_datetime("2017-03-31 23:59:59")),
        (pd.to_datetime("2017-04-01 00:00:00"), pd.to_datetime("2017-09-30 23:59:59")),
        (pd.to_datetime("2017-10-01 00:00:00"), pd.to_datetime("2018-03-31 23:59:59")),
        (pd.to_datetime("2018-04-01 00:00:00"), pd.to_datetime("2018-09-30 23:59:59")),
        (pd.to_datetime("2018-10-01 00:00:00"), pd.to_datetime("2019-03-31 23:59:59")),
        (pd.to_datetime("2019-01-01 00:00:00"), pd.to_datetime("2019-03-31 23:59:59")),
        (pd.to_datetime("2019-04-01 00:00:00"), pd.to_datetime("2019-09-30 23:59:59")),
        (pd.to_datetime("2019-10-01 00:00:00"), pd.to_datetime("2020-03-31 23:59:59")),
        (pd.to_datetime("2020-04-01 00:00:00"), pd.to_datetime("2020-09-30 23:59:59")),
        (pd.to_datetime("2020-10-01 00:00:00"), pd.to_datetime("2021-03-31 23:59:59")),
        (pd.to_datetime("2021-04-01 00:00:00"), pd.to_datetime("2021-09-30 23:59:59")),
        (pd.to_datetime("2021-10-01 00:00:00"), pd.to_datetime("2022-03-31 23:59:59")),
        (pd.to_datetime("2022-04-01 00:00:00"), pd.to_datetime("2022-09-30 23:59:59")),
        (pd.to_datetime("2022-10-01 00:00:00"), pd.to_datetime("2022-12-31 23:59:59")),
        (pd.to_datetime("2023-01-01 00:00:00"), pd.to_datetime("2023-03-31 23:59:59")),
        (pd.to_datetime("2023-04-01 00:00:00"), pd.to_datetime("2023-06-30 23:59:59")),
        (pd.to_datetime("2023-07-01 00:00:00"), pd.to_datetime("2023-09-30 23:59:59")),
        (pd.to_datetime("2023-10-01 00:00:00"), pd.to_datetime("2023-12-31 23:59:59")),
        (pd.to_datetime("2024-01-01 00:00:00"), pd.to_datetime("2024-03-31 23:59:59")),
        (pd.to_datetime("2024-04-01 00:00:00"), pd.to_datetime("2024-06-30 23:59:59")),
        (pd.to_datetime("2024-07-01 00:00:00"), pd.to_datetime("2024-09-30 23:59:59")),
        (pd.to_datetime("2024-10-01 00:00:00"), pd.to_datetime("2024-12-31 23:59:59")),
        (pd.to_datetime("2025-01-01 00:00:00"), pd.to_datetime("2025-03-31 23:59:59")),
        (pd.to_datetime("2025-04-01 00:00:00"), pd.to_datetime("2025-06-30 23:59:59")),
        (pd.to_datetime("2025-07-01 00:00:00"), pd.to_datetime("2025-09-30 23:59:59")),
        (pd.to_datetime("2025-10-01 00:00:00"), pd.to_datetime("2025-12-31 23:59:59")),
        (pd.to_datetime("2026-01-01 00:00:00"), pd.to_datetime("2026-03-31 23:59:59")),
        (pd.to_datetime("2026-04-01 00:00:00"), pd.to_datetime("2026-06-30 23:59:59")),
        (pd.to_datetime("2026-07-01 00:00:00"), pd.to_datetime("2026-09-30 23:59:59")),
        (pd.to_datetime("2026-10-01 00:00:00"), pd.to_datetime("2026-12-31 23:59:59")),
        (pd.to_datetime("2027-01-01 00:00:00"), pd.to_datetime("2027-03-31 23:59:59")),
        (pd.to_datetime("2027-04-01 00:00:00"), pd.to_datetime("2027-06-30 23:59:59")),
        (pd.to_datetime("2027-07-01 00:00:00"), pd.to_datetime("2027-09-30 23:59:59")),
        (pd.to_datetime("2027-10-01 00:00:00"), pd.to_datetime("2027-12-31 23:59:59")),
        (pd.to_datetime("2028-01-01 00:00:00"), pd.to_datetime("2028-03-31 23:59:59")),
        (pd.to_datetime("2028-04-01 00:00:00"), pd.to_datetime("2028-06-30 23:59:59")),
        (pd.to_datetime("2028-07-01 00:00:00"), pd.to_datetime("2028-09-30 23:59:59")),
        (pd.to_datetime("2028-10-01 00:00:00"), pd.to_datetime("2028-12-31 23:59:59")),
        (pd.to_datetime("2029-01-01 00:00:00"), pd.to_datetime("2029-03-31 23:59:59")),
        (pd.to_datetime("2029-04-01 00:00:00"), pd.to_datetime("2029-06-30 23:59:59")),
        (pd.to_datetime("2029-07-01 00:00:00"), pd.to_datetime("2029-09-30 23:59:59")),
        (pd.to_datetime("2029-10-01 00:00:00"), pd.to_datetime("2029-12-31 23:59:59")),
        (pd.to_datetime("2030-01-01 00:00:00"), pd.to_datetime("2030-03-31 23:59:59")),
        (pd.to_datetime("2030-04-01 00:00:00"), pd.to_datetime("2030-06-30 23:59:59")),
        (pd.to_datetime("2030-07-01 00:00:00"), pd.to_datetime("2030-09-30 23:59:59")),
        (pd.to_datetime("2030-10-01 00:00:00"), pd.to_datetime("2030-12-31 23:59:59")),
    ],
    closed="both",
    name="28AD Charge Restriction Period 3 Month",
)

index_28AD = pd.MultiIndex.from_arrays([_outer_idx, _inner_idx])


# Functions for getting and processing Annex 4 data


def download_annex_4(
    url: str = config.get("data_sources").get("ofgem_annex_4"),
    as_fileobject: bool = False,
) -> Optional[BytesIO]:
    """Retrieves annex4 xlsx file from Ofgem website and either saves to a file or returns a fileobject.

    Args:
        url: str, url of relevant Ofgem Annex 4 xlsx file. Defaults to entry in config.
        as_fileobject: bool (default: False), whether to save to disk or return BytesIO fileobject.

    Returns:
        Optionally, None or BytesIO fileobject.
    """
    with Session() as session:
        try:
            response = session.get(url)
            if not as_fileobject:
                date = datetime.datetime.now().strftime("%Y%m%d")
                with open(f"{DATA_ROOT}{date}_ofgem_annex_4.xlsx", mode="wb") as file:
                    file.write(response.content)
            else:
                return BytesIO(response.content)
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


def _get_excel_sheet_names(file_path: Union[str, BytesIO]) -> list:
    """Gets xlsx sheet names quickly for file or fileobject.

    Args:
        file_path: str or BytesIO, filepath or fileobject for excel xlsx file.

    Returns:
        List of sheet names.
    """
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        xml = zip_ref.read("xl/workbook.xml").decode("utf-8")
    sheets = []
    for s_tag in re.findall("<sheet [^>]*", xml):
        sheets.append(re.search('name="[^"]*', s_tag).group(0)[6:])
    return sheets


def _get_raw_dataframe_annex4(
    policy_name: str, fileobject: Optional[BytesIO] = None
) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 4
    spreadsheet tab corresponding to policy of interest.

    Args:
        policy_name: str, identifier for policy of interest. Must be reference as tab in Annex 4.
        fileobject: None or BytesIO, fileobject if working in memory else None.

    Returns:
        pandas DataFrame of Annex 4 data for specified policy_name.
    """
    if not fileobject:
        date = datetime.datetime.now()
        latest_annex_4 = _find_latest_annex(DATA_ROOT, 4)
        if (
            day_diff := (
                date - datetime.datetime.strptime(latest_annex_4, "%Y%m%d")
            ).days
        ) > 7:
            warnings.warn(f"Using copy of Annex 4 downloaded {day_diff} days ago.")
        filepath = f"{DATA_ROOT}{latest_annex_4}_ofgem_annex_4.xlsx"
        try:
            sheet = [
                sheet_name
                for sheet_name in _get_excel_sheet_names(filepath)
                if policy_name in sheet_name
            ][0]
        except:
            raise ValueError("Acronym given does not correspond to a valid policy.")

        return pd.read_excel(
            filepath,
            sheet_name=sheet,
            skiprows=4,
            header=1,
            index_col=0,
            engine="calamine",
        ).reset_index(drop=True)
    else:
        try:
            sheet = [
                sheet_name
                for sheet_name in _get_excel_sheet_names(fileobject)
                if policy_name in sheet_name
            ][0]
        except:
            raise ValueError("Acronym given does not correspond to a valid policy.")
        return pd.read_excel(
            fileobject,
            sheet_name=sheet,
            skiprows=4,
            header=1,
            index_col=0,
            engine="calamine",
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
        print(f"Number of entries: {len(update_dates)}")
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
    policy_acronym: str,
    policy_parameters: list,
    column_names: list,
    fileobject: Optional[BytesIO] = None,
) -> pd.DataFrame:
    """Generic function for returning processed annex 4 data."""
    # Create dataframe of raw RO data from spreadsheet tab
    df = _get_raw_dataframe_annex4(policy_acronym, fileobject)
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
    # Add 28AD charge restriction index
    data_tidy_df = data_tidy_df.set_index(index_28AD)

    return data_tidy_df


def process_data_RO(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
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
    return _process_data("RO", parameters, names, fileobject)


def process_data_WHD(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
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
    return _process_data("WHD", parameters, names, fileobject)


def process_data_AAHEDC(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
    """Extracts and transforms data from corresponding AAHEDC tab in annex 4 into tidy format."""
    parameters = [
        "Final AAHEDC tariff for current charging year",
        "Final AAHEDC tariff for previous charging year",
        "Forecast of annual RPI for previous charging year",
    ]
    names = ["TariffCurrentYear", "TariffPreviousYear", "ForecastAnnualRPIPreviousYear"]
    return _process_data("AAHEDC", parameters, names, fileobject)


def process_data_GGL(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
    """Extracts and transforms data from corresponding GGL tab in annex 4 into tidy format."""
    parameters = ["Levy rate", "Backdated levy rate for first scheme year"]
    names = ["LevyRate", "BackdatedLevyRate"]
    return _process_data("GGL", parameters, names, fileobject)


def process_data_ECO(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
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

    eco_df = _process_data("ECO", parameters, names, fileobject)

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


def process_data_FIT(fileobject: Optional[BytesIO] = None) -> pd.DataFrame:
    """Extracts and transforms data from corresponding New FIT tab in annex 4 into tidy format."""
    # Create dataframe of raw FIT data from spreadsheet tab
    FIT_df = _get_raw_dataframe_annex4("New FIT", fileobject)
    # Create list of lookup periods (Table 5)
    lookup_periods = _get_lookup_periods(FIT_df)
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
            pd.Series(lookup_periods, name="LookupPeriod"),
        ]
        + [
            pd.Series(FIT_parameters[i], name=parameter)
            for i, parameter in enumerate(column_names)
        ],
        axis=1,
    )

    # Add 28AD index
    data_tidy_df = data_tidy_df.set_index(index_28AD[3:])
    # backfill 3 missing rows to match other levies
    data_tidy_df = pd.concat(
        [
            pd.DataFrame(
                np.full((3, len(data_tidy_df.columns)), np.nan),
                columns=data_tidy_df.columns,
            ).set_index(index_28AD[:3]),
            data_tidy_df,
        ]
    )

    return data_tidy_df


# Functions for getting and processing Annex 9 data


def download_annex_9(
    url: str = config.get("data_sources").get("ofgem_annex_9"),
    as_fileobject: bool = False,
) -> Optional[BytesIO]:
    """Retrieves annex9 xlsx file from Ofgem website and either saves to a file or returns a fileobject.

    Args:
        url: str, url of relevant Ofgem Annex 9 xlsx file. Defaults to url in config.
        as_fileobject: bool (default: False), whether to save to disk or return BytesIO fileobject.

    Returns:
        Optionally, None or BytesIO fileobject.
    """
    with Session() as session:
        try:
            response = session.get(url)
            if not as_fileobject:
                date = datetime.datetime.now().strftime("%Y%m%d")
                with open(f"{DATA_ROOT}{date}_ofgem_annex_9.xlsx", mode="wb") as file:
                    file.write(response.content)
            else:
                return BytesIO(response.content)
            print("File retrieved successfully.")
        except RequestException as rex:
            print("Failed to download annex 9", rex)


def _get_raw_dataframe_annex9(
    data_name: str, fileobject: Optional[BytesIO] = None
) -> pd.DataFrame:
    """Creates a pandas dataframe of raw data from Ofgem Annex 9
    spreadsheet tab corresponding to policy of interest."""
    if not fileobject:
        date = datetime.datetime.now()
        latest_annex_9 = _find_latest_annex(DATA_ROOT, 9)
        if (
            day_diff := (
                date - datetime.datetime.strptime(latest_annex_9, "%Y%m%d")
            ).days
        ) > 7:
            warnings.warn(f"Using copy of Annex 9 downloaded {day_diff} days ago.")
        filepath = f"{DATA_ROOT}{latest_annex_9}_ofgem_annex_9.xlsx"
        try:
            sheet = [
                sheet_name
                for sheet_name in _get_excel_sheet_names(filepath)
                if data_name in sheet_name
            ][0]
        except:
            raise ValueError(
                "Input does not correspond to a valid tab in the spreadsheet."
            )

        return pd.read_excel(
            filepath, sheet_name=sheet, header=1, index_col=0, engine="calamine"
        ).reset_index(drop=True)
    else:
        try:
            sheet = [
                sheet_name
                for sheet_name in _get_excel_sheet_names(fileobject)
                if data_name in sheet_name
            ][0]
        except:
            raise ValueError(
                "Input does not correspond to a valid tab in the spreadsheet."
            )

        return pd.read_excel(
            fileobject, sheet_name=sheet, header=1, index_col=0, engine="calamine"
        ).reset_index(drop=True)


def _slice_tariff_components_tables(
    sheet_start_row: int,
    levelisation: bool,
    fileobject: Optional[BytesIO] = None,
) -> pd.DataFrame:
    """Extracts tariff components tables of interest from Annex 9 tab "1c Consumption adjusted levels".

    Parameters
    ----------
    sheet_start_row : int
        Row number of header row in target tables in sheet "1c Consumption adjusted levels".
    levelisation : bool
        Boolean representing whether "Levelisation" tariff component is included in tariff table of interest.
    fileobject : BytesIO or None
        BytesIO fileobject if working in memory else None.

    Returns
    -------
    pd.DataFrame
        Dataframe of tariff components tables of interest.
    """

    # Create dataframe of raw consumption adjusted level costs from spreadsheet tab
    consumption_adjusted_levels_df = _get_raw_dataframe_annex9(
        "Consumption adjusted levels", fileobject
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


def _extract_single_tariff_table(
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
    with warnings.catch_warnings():
        # Suppress Future warning for replace.
        warnings.simplefilter("ignore")
        single_tariff_table_df = single_tariff_table_df.replace(
            "[\u002D\u058A\u05BE\u1400\u1806\u2010-\u2015\u2E17\u2E1A\u2E3A\u2E3B\u2E40\u301C\u3030\u30A0\uFE31\uFE32\uFE58\uFE63\uFF0D]",
            None,
            regex=True,
        )
    return single_tariff_table_df


def _tidy_tariff_table(
    input_df: pd.DataFrame, type_of_consumption: str
) -> pd.DataFrame:
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
    # Transpose table to put 28ad charging period in the index
    df = input_df.set_index(type_of_consumption).transpose().reset_index()
    # Get starting period of the table
    starting_period = pd.to_datetime(df.loc[0, "index"].split("-")[0])
    # Get index starting point
    try:
        start_index = (
            index_28AD.map(lambda idx: True if starting_period in idx[1] else False)
            .to_numpy()
            .nonzero()[0][0]
        )
    except IndexError:
        raise IndexError("Could not match tariff start date with 28AD index.")
    # set multi index
    # Remove Jan 2019 record - this isn't used for tariffs.
    drop_idx = (
        index_28AD.map(
            lambda idx: True if pd.to_datetime("2019-01") in idx[1] else False
        )
        .to_numpy()
        .nonzero()[0][1]
    )
    # Add index to table - dropping unneeded row and limiting to relevant period.
    df = df.set_index(
        index_28AD.drop(index_28AD[drop_idx])[start_index : start_index + df.shape[0]]
    )

    tidy_df = (
        df.drop(columns="index")
        .reset_index()
        .melt(
            id_vars=[
                "28AD Charge Restriction Period 6 Month",
                "28AD Charge Restriction Period 3 Month",
            ]
        )
        .set_index(
            [
                "28AD Charge Restriction Period 6 Month",
                "28AD Charge Restriction Period 3 Month",
            ]
        )
    )

    return tidy_df


def _process_tariff(
    sheet_start_row: int,
    levelisation: bool,
    type_of_consumption: str,
    table_number: int,
    fileobject: Optional[BytesIO] = None,
) -> pd.DataFrame:
    """Generic function for returning processed tariff component data from annex 9.

    Parameters
    ----------
    sheet_start_row : int
        Row number of header row in target tables in sheet "1c Consumption adjusted levels".
    levelisation : bool
        Boolean representing whether "Levelisation" tariff component is included in tariff table of interest.
    type_of_consumption : str
        "Nil consumption" or "Typical consumption" ONLY.
    table_number : int
        1: Electricity single-rate; 2: Electricity multi-register; 3: Gas; 4: Duel fuel
    fileobject : BytesIO or None
        BytesIO fileobject if working in memory else None.
    """
    return _tidy_tariff_table(
        _extract_single_tariff_table(
            _slice_tariff_components_tables(sheet_start_row, levelisation, fileobject),
            type_of_consumption,
            table_number,
        ),
        type_of_consumption,
    )


## Standard Credit
# Electricity
def process_tariff_elec_standard_credit_nil(fileobject: Optional[BytesIO] = None):
    """Extracts and transforms Standard Credit tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Nil consumption."""
    sheet_start_row = 55
    levelisation = False
    type_of_consumption = "Nil consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_elec_standard_credit_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Standard Credit tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Typical consumption."""
    sheet_start_row = 70
    levelisation = False
    type_of_consumption = "Typical consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


# Gas
def process_tariff_gas_standard_credit_nil(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Standard Credit tariff component data from annex 9 for Gas, Nil consumption."""
    sheet_start_row = 55
    levelisation = False
    type_of_consumption = "Nil consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_gas_standard_credit_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Standard Credit tariff component data from annex 9 for Gas, Typical consumption."""
    sheet_start_row = 70
    levelisation = False
    type_of_consumption = "Typical consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


## Other payment method
# Electricity
def process_tariff_elec_other_payment_nil(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Other Payment Method tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Nil consumption."""
    sheet_start_row = 19
    levelisation = True
    type_of_consumption = "Nil consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_elec_other_payment_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Other Payment Method tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Typical consumption."""
    sheet_start_row = 35
    levelisation = True
    type_of_consumption = "Typical consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


# Gas
def process_tariff_gas_other_payment_nil(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Other Payment Method tariff component data from annex 9 for Gas, Nil consumption."""
    sheet_start_row = 19
    levelisation = True
    type_of_consumption = "Nil consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_gas_other_payment_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms Other Payment Method tariff component data from annex 9 for Gas, Typical consumption."""
    sheet_start_row = 35
    levelisation = True
    type_of_consumption = "Typical consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


## PPM
# Electricity
def process_tariff_elec_ppm_nil(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms PPM tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Nil consumption."""
    sheet_start_row = 88
    levelisation = True
    type_of_consumption = "Nil consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_elec_ppm_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms PPM tariff component data from annex 9 for Electricity: Single-Rate Metering Arrangement, Typical consumption."""
    sheet_start_row = 104
    levelisation = True
    type_of_consumption = "Typical consumption"
    table_number = 1
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


# Gas
def process_tariff_gas_ppm_nil(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms PPM tariff component data from annex 9 for Gas, Nil consumption."""
    sheet_start_row = 88
    levelisation = True
    type_of_consumption = "Nil consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def process_tariff_gas_ppm_typical(
    fileobject: Optional[BytesIO] = None,
):
    """Extracts and transforms PPM tariff component data from annex 9 for Gas, Typical consumption."""
    sheet_start_row = 104
    levelisation = True
    type_of_consumption = "Typical consumption"
    table_number = 3
    return _process_tariff(
        sheet_start_row, levelisation, type_of_consumption, table_number, fileobject
    )


def _ofgem_archetypes_dataset(descriptor: str) -> pd.DataFrame:
    """Helper function to generate a dataframe with Ofgem archetype data from a .pkl file. The .pkl is a dictionary of dataframes with the following keys:
    headline, scheme eligibility, equivalised income deciles, net income deciles, retired or pension, full data by net income decile, benefit recipients, in poverty.
    """
    master_df = pd.read_pickle(f"{ARCHETYPE_DATA_ROOT}master_archetypes_data.pkl")
    return master_df[descriptor]


def ofgem_archetypes_data() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype headline data."""
    return _ofgem_archetypes_dataset("headline")


def ofgem_archetypes_scheme_eligibility() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on numberof households eligible for various schemes."""
    return _ofgem_archetypes_dataset("scheme eligibility")


def ofgem_archetypes_equivalised_income_deciles() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on number of households in each OECD equivalised income decile."""
    return _ofgem_archetypes_dataset("equivalised income deciles")


def ofgem_archetypes_net_income_deciles() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on number of households in each net income decile."""
    return _ofgem_archetypes_dataset("net income deciles")


def ofgem_archetypes_retired_pension() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on number of households with retired economic status or
    in receipt of pension guarantee/savings credit."""
    return _ofgem_archetypes_dataset("retired or pension")


def ofgem_archetypes_net_income_deciles_full() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype detailed data on income, heating fuel, energy consumption, unmetered fuel spend
    and number of households by archetype and income decile."""
    return _ofgem_archetypes_dataset("full data by net income decile")


def ofgem_archetypes_benefit_recipients() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on number of households in receipt of child benefit or universal credit."""
    return _ofgem_archetypes_dataset("benefit recipients")


def ofgem_archetypes_in_poverty() -> pd.DataFrame:
    """Pre-filled function to generate a dataframe with Ofgem archetype data on number of households below the poverty line (income below 60% of median) after housing costs and before housing costs."""
    return _ofgem_archetypes_dataset("in poverty")
