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
