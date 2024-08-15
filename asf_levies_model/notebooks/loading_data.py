# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     comment_magics: true
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: asf_levies_model
#     language: python
#     name: python3
# ---

# %% [markdown]
# ### **Getting data inputs for core model**

# %% [markdown]
# Running this file saves the following parquet files in inputs/data:
# - Policy cost input data (RO, WHD, ECO, AAHEDC, GGL, FIT)
# - Default tariff component costs (Standard Credit, Gas and Electricity (Single-rate), Nil and Typical consumption)
# - Gas and electricity consumption values (typical and for each Ofgem energy archetype)
# - Gas and electricity supply volumes from DUKES and Subnational Consumption Statistics
# - Gas and electricity meter points from Subnational Consumption Statistics

# %% [markdown]
# #### **Getting data from Annex 4: Policy cost allowance methodology**

# %%
import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa

from asf_levies_model.getters.load_data import (
    download_annex_4,
    process_data_RO,
    process_data_WHD,
    process_data_ECO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_FIT,
    validate_input_data,
)

import asf_levies_model.config.data_config as data_config

from asf_levies_model import PROJECT_DIR

# %% [markdown]
# **1. Download most recent Annex 4: Policy cost allowance methodology file**

# %%
# Copy and paste URL for most recent Annex 4 release
url = "https://www.ofgem.gov.uk/sites/default/files/2024-03/Annex_4_-_Policy_cost_allowance_methodology_v1.18.xlsx"
download_annex_4(url)

# %% [markdown]
# **2. Extract and transform data for each policy into tidy format.**

# %% [markdown]
# (i) Renewables Obligation (RO)

# %%
# Create dataframe of input data in tidy format
RO_data = process_data_RO()

# Validate data types in each column
validate_input_data(RO_data, data_config.RO_schema)

# %%
# Save to file

data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

RO_data.to_parquet(f"{data_root}{date}_RO_data_tidy.parquet")

# %% [markdown]
# (ii) Warm Home Discount (WHD)

# %%
# Create dataframe of input data in tidy format
WHD_data = process_data_WHD()

# Validate data types in each column
validate_input_data(WHD_data, data_config.WHD_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

WHD_data.to_parquet(f"{data_root}{date}_WHD_data_tidy.parquet")

# %% [markdown]
# (iii) Energy Company Obligation (ECO)

# %%
# Create dataframe of input data in tidy format
ECO_data = process_data_ECO()

# Validate data types in each column
validate_input_data(ECO_data, data_config.ECO_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

ECO_data.to_parquet(f"{data_root}{date}_ECO_data_tidy.parquet")

# %% [markdown]
# (iv) Assistance for Areas with High Electricity Distribution Costs (AAHEDC)

# %%
# Create dataframe of input data in tidy format
AAHEDC_data = process_data_AAHEDC()

# Validate data types in each column
validate_input_data(AAHEDC_data, data_config.AAHEDC_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

AAHEDC_data.to_parquet(f"{data_root}{date}_AAHEDC_data_tidy.parquet")

# %% [markdown]
# (v) Green Gas Levy (GGL)

# %%
# Create dataframe of input data in tidy format
GGL_data = process_data_GGL()

# Validate data types in each column
validate_input_data(GGL_data, data_config.GGL_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

GGL_data.to_parquet(f"{data_root}{date}_GGL_data_tidy.parquet")

# %% [markdown]
# (vi) Feed-in Tariffs (FIT)
# - Different formatting and more complex use of inputs compared to other five levies

# %%
# Create dataframe of input data in tidy format
FIT_data = process_data_FIT()

# Validate data types in each column
validate_input_data(FIT_data, data_config.FIT_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

FIT_data.to_parquet(f"{data_root}{date}_FIT_data_tidy.parquet")

# %% [markdown]
# #### **Getting data from Annex 9: Levelisation Allowance methodology and levelised cap levels**

# %%
import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa

from asf_levies_model.getters.load_data import (
    download_annex_9,
    slice_tariff_components_tables,
    extract_single_tariff_table,
    tidy_tariff_table,
    validate_input_data,
    get_typical_consumption_values,
)

import asf_levies_model.config.data_config as data_config

from asf_levies_model import PROJECT_DIR

# %% [markdown]
# **1. Download most recent Annex 9: Levelisation Allowance methodology and levelised cap levels**

# %%
# Copy and paste URL for most recent Annex 4 release
url = "https://www.ofgem.gov.uk/sites/default/files/2024-05/Annex%209%20-%20Levelisation%20allowance%20methodology%20and%20levelised%20cap%20levels%20v1.2.xlsx"
download_annex_9(url)

# %% [markdown]
# **2. Extract and transform data into tidy format.**

# %% [markdown]
# (i) Historical default tariff components from consumption adjusted levels tables: **Standard Credit**

# %% [markdown]
# *As of Aug 2024, the order of tables for each payment method (Other Payment Method/Standard Credit/PPM):*
# 1. Electricity: Single-Rate Metering Arrangement
# 2. Electricity: Multi-Register Metering Arrangement
# 3. Gas

# %%
# Slice Standard Credit Nil Consumption tables
standard_credit_nil_consumption_df = slice_tariff_components_tables(
    sheet_start_row=55, levelisation=False
)

# Slice Standard Credit Typical Consumption tables
standard_credit_typical_consumption_df = slice_tariff_components_tables(
    sheet_start_row=70, levelisation=False
)

# %% [markdown]
# Electricity - Single-Rate Metering Arrangement (Table 1)

# %%
# Slice Electricity: Single-Rate Metering Arrangement table - Nil consumption
electricity_single_nil_df = extract_single_tariff_table(
    standard_credit_nil_consumption_df,
    "Nil consumption",
    table_number=1,
    number_of_time_periods=19,
)

# Create a dataframe containing data in tidy format
electricity_single_rate_nil = tidy_tariff_table(
    electricity_single_nil_df, "Nil consumption", levelisation=False
)

# Validate data types
validate_input_data(
    electricity_single_rate_nil,
    data_config.tariff_components_without_levelisation_schema,
)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

electricity_single_rate_nil.to_parquet(
    f"{data_root}{date}_electricity_single_rate_nil_tariff.parquet"
)

# %%
# Slice Electricity: Single-Rate Metering Arrangement table - Typical consumption
electricity_single_typical_df = extract_single_tariff_table(
    standard_credit_typical_consumption_df,
    "Typical consumption",
    table_number=1,
    number_of_time_periods=19,
)

# Create a dataframe containing data in tidy format
electricity_single_rate_typical = tidy_tariff_table(
    electricity_single_typical_df, "Typical consumption", levelisation=False
)

# Validate data types
validate_input_data(
    electricity_single_rate_typical,
    data_config.tariff_components_without_levelisation_schema,
)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

electricity_single_rate_typical.to_parquet(
    f"{data_root}{date}_electricity_single_rate_typical_tariff.parquet"
)

# %% [markdown]
# Gas (Table 3)

# %%
# Slice Gas table - Nil consumption
gas_nil_df = extract_single_tariff_table(
    standard_credit_nil_consumption_df,
    "Nil consumption",
    table_number=3,
    number_of_time_periods=19,
)

# Create a dataframe containing data in tidy format
gas_nil = tidy_tariff_table(gas_nil_df, "Nil consumption", levelisation=False)

# Validate data types
validate_input_data(gas_nil, data_config.tariff_components_without_levelisation_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

gas_nil.to_parquet(f"{data_root}{date}_gas_nil_tariff_data.parquet")

# %%
# Slice Gas table - Typical consumption
gas_typical_df = extract_single_tariff_table(
    standard_credit_typical_consumption_df,
    "Typical consumption",
    table_number=3,
    number_of_time_periods=19,
)

# Create a dataframe containing data in tidy format
gas_typical = tidy_tariff_table(
    gas_typical_df, "Typical consumption", levelisation=False
)

# Validate data types
validate_input_data(
    gas_typical, data_config.tariff_components_without_levelisation_schema
)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

gas_typical.to_parquet(f"{data_root}{date}_gas_typical_tariff_data.parquet")

# %% [markdown]
# (ii) Typical energy consumption values

# %%
# Create dataframe containing data
typical_consumption_values_tidy_df = get_typical_consumption_values(
    sheet_start_row=6, sheet_start_col=2
)

# Validate data types
validate_input_data(
    typical_consumption_values_tidy_df, data_config.typical_consumption_values_schema
)

# %% [markdown]
# #### **Getting data from Ofgem energy consumer archetypes update 2024**

# %%
import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa

from asf_levies_model.getters.load_data import (
    get_ofgem_archetypes_data,
    combine_consumption_values,
    validate_input_data,
)

import asf_levies_model.config.data_config as data_config

from asf_levies_model import PROJECT_DIR

# %% [markdown]
# **1. Load data and create clean dataframe**

# %%
# Create dataframe with Ofgem energy archetypes data
ofgem_archetypes_df = get_ofgem_archetypes_data()

# Validate data types
validate_input_data(ofgem_archetypes_df, data_config.ofgem_archetypes_schema)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

ofgem_archetypes_df.to_parquet(f"{data_root}{date}_ofgem_archetypes_data.parquet")

# %% [markdown]
# **2. Append to main consumption values table**

# %%
# Append relevant data to main consumption dataframe with typical values
consumption_values_tidy_df = combine_consumption_values(
    ofgem_archetypes_df, typical_consumption_values_tidy_df
)

# %%
# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

consumption_values_tidy_df.to_parquet(f"{data_root}{date}_consumption_values.parquet")

# %% [markdown]
# #### **Getting data from DUKES 2024**

# %%
import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa

from asf_levies_model.getters.load_data import download_dukes, get_dukes_supply_data

import asf_levies_model.config.data_config as data_config

from asf_levies_model import PROJECT_DIR

# %% [markdown]
# DUKES 4.1 Natural gas commodity balance and DUKES 5.2 Electricity commodity balances, public distribution system and other generators

# %%
# Copy and paste URL for most recent DUKES 4.1
url = "https://assets.publishing.service.gov.uk/media/66a7aebe49b9c0597fdb0684/DUKES_4.1.xlsx"
download_dukes(url, "4_1")

# Copy and paste URL for most recent DUKES 5.2
url = "https://assets.publishing.service.gov.uk/media/66a7da36ce1fd0da7b592f0c/DUKES_5.2.xlsx"
download_dukes(url, "5_2")

# %%
dukes_year = "2023"

dukes_total_gas, dukes_domestic_gas, dukes_total_elec, dukes_domestic_elec = (
    get_dukes_supply_data(dukes_year)
)

# %% [markdown]
# #### **Getting data from Regional and local authority consumption statistics**

# %%
import requests
import pandas as pd
import datetime
import numpy as np
import math
import pandera as pa

from asf_levies_model.getters.load_data import (
    download_subnational_consumption,
    get_subnational_consumption_data,
)

import asf_levies_model.config.data_config as data_config

from asf_levies_model import PROJECT_DIR

# %%
# Copy and paste URL for most recent subnational gas consumption statistics file (non-weather-corrected)
url = "https://assets.publishing.service.gov.uk/media/65b030021702b1000dcb111b/Subnational_gas_consumption_statistics_non_weather_corrected_2015-2022.xlsx"
download_subnational_consumption(url, "gas")

# %%
# Copy and paste URL for most recent subnational electricity consumption statistics file
url = "https://assets.publishing.service.gov.uk/media/65b024e0160765000d18f73c/Subnational_electricity_consumption_statistics_2005-2022.xlsx"
download_subnational_consumption(url, "electricity")

# %%
subnational_year = "2022"
(
    subnational_total_gas_meters,
    subnational_domestic_gas_meters,
    subnational_total_gas,
    subnational_domestic_gas,
    subnational_total_elec_meters,
    subnational_domestic_elec_meters,
    subnational_total_elec,
    subnational_domestic_elec,
) = get_subnational_consumption_data(subnational_year)

# %% [markdown]
# Compiling all supply volume and meter points data

# %%
# Create dataframe
supply_volume_dict = {
    "DUKESYear": pd.Series(dukes_year),
    "DUKESTotalGas": pd.Series(dukes_total_gas),
    "DUKESTotalElec": pd.Series(dukes_total_elec),
    "DUKESDomesticGas": pd.Series(dukes_domestic_gas),
    "DUKESDomesticElec": pd.Series(dukes_domestic_elec),
    "SubnationalYear": pd.Series(subnational_year),
    "SubnationalTotalGas": pd.Series(subnational_total_gas),
    "SubnationalTotalElec": pd.Series(subnational_total_elec),
    "SubnationalDomesticGas": pd.Series(subnational_domestic_gas),
    "SubnationalDomesticElec": pd.Series(subnational_domestic_elec),
}
supply_volumes = pd.DataFrame(supply_volume_dict)  # All values in MWh

# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")
supply_volumes.to_parquet(f"{data_root}{date}_supply_volume_data.parquet")

# %% [markdown]
# Compiling meter points data

# %%
# Create dataframe
meter_points_dict = {
    "SubnationalYear": pd.Series(subnational_year),
    "SubnationalTotalMetersGas": pd.Series(subnational_total_gas_meters),
    "SubnationalTotalMetersElec": pd.Series(subnational_total_elec_meters),
    "SubnationalDomesticMetersGas": pd.Series(subnational_domestic_gas_meters),
    "SubnationalDomesticMetersElec": pd.Series(subnational_domestic_elec_meters),
}
meter_points = pd.DataFrame(meter_points_dict)

# Save to file
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

meter_points.to_parquet(f"{data_root}{date}_meter_points_data.parquet")
