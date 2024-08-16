# %%
import pandas as pd
import datetime
import math

from asf_levies_model import PROJECT_DIR

# %% [markdown]
# Open this file as a Jupyter notebook. <br>
# Run "loading_data.py" to get and save data files with today's date in the file names.

# %%
# Run to generate today's data files
# %run -i loading_data.py

# %%
data_root = f"{PROJECT_DIR}/inputs/data/analysis_cache/"
date = datetime.datetime.now().strftime("%Y%m%d")

# %% [markdown]
# **Typical consumption values**

# %%
tcv_df = pd.read_parquet(f"{data_root}{date}_consumption_values.parquet")
tcv = tcv_df.iloc[0]
tcv

# %% [markdown]
# **Electricity and gas supply and meter point values**

# %%
supply_volumes = pd.read_parquet(f"{data_root}{date}_supply_volume_data.parquet")
supply_volumes  # MWh

# %%
total_elec_2023 = supply_volumes.DUKESTotalElec[0] * 1000  # GWh -> MWh
total_gas_2023 = supply_volumes.DUKESTotalGas[0] * 1000  # GWh -> MWh
domestic_elec_2023 = supply_volumes.DUKESDomesticElec[0] * 1000  # GWh -> MWh
domestic_gas_2023 = supply_volumes.DUKESDomesticGas[0] * 1000  # GWh -> MWh

# %%
meter_points = pd.read_parquet(f"{data_root}{date}_meter_points_data.parquet")
meter_points  # meters

# %%
total_meters_2022_elec = meter_points.SubnationalTotalMetersElec[0]
total_meters_2022_gas = meter_points.SubnationalTotalMetersGas[0]
domestic_meters_2022_elec = meter_points.SubnationalDomesticMetersElec[0]
domestic_meters_2022_gas = meter_points.SubnationalDomesticMetersGas[0]

# %% [markdown]
# #### Calculations for each policy

# %%
# Scrappy function to demo essential calculations


def calculate_policy_cost_contribution(
    fixed_weight,
    variable_weight,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
):

    # Revenue contributions
    revenue_gas = target_revenue * gas_weight
    revenue_elec = target_revenue * elec_weight
    revenue_tax = target_revenue * tax_weight

    # New variable levy rate
    new_levy_var_gas = (revenue_gas / supply_gas) * variable_weight
    new_levy_var_elec = (revenue_elec / supply_elec) * variable_weight

    print(f"New levy rate (gas) - variable: {new_levy_var_gas}")
    print(f"New levy rate (elec) - variable: {new_levy_var_elec}")

    # New fixed levy rate
    new_levy_fixed_gas = (revenue_gas / customers_gas) * fixed_weight
    new_levy_fixed_elec = (revenue_elec / customers_elec) * fixed_weight

    print(f"New levy rate (gas) - fixed: {new_levy_fixed_gas}")
    print(f"New levy rate (elec) - fixed: {new_levy_fixed_elec}")

    # New revenue contributions - for checks
    new_revenue_gas = (new_levy_var_gas * supply_gas) + (
        new_levy_fixed_gas * customers_gas
    )
    new_revenue_elec = (new_levy_var_elec * supply_elec) + (
        new_levy_fixed_elec * customers_elec
    )

    # Check revenue is maintained
    print(
        f"Revenue : {(new_revenue_gas + new_revenue_elec + revenue_tax)/1e6, (target_revenue)/1e6 } million £"
    )

    # New bill
    bill_gas = (new_levy_var_gas * (tcv.GaskWh / 1e3)) + new_levy_fixed_gas
    bill_elec = (
        new_levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3)
    ) + new_levy_fixed_elec

    bill_new = bill_gas + bill_elec

    print(f"New bill: {bill_new} (Current bill: {bill_current})")
    print(f"Amount for general taxation: {revenue_tax/1e6} million £")

    return bill_new


# %% [markdown]
# ---

# %% [markdown]
# **RO**

# %%
# Load data from file
ro_data = pd.read_parquet(f"{data_root}{date}_RO_data_tidy.parquet")
current_row = ro_data.index[ro_data["UpdateDate"] == "February 2024"][0]
ro = ro_data.iloc[current_row, :]
ro

# %% [markdown]
# From: https://www.gov.uk/government/publications/renewables-obligation-level-calculations-2024-to-2025/calculating-the-level-of-the-renewables-obligation-for-2024-to-2025

# %%
ro_elec_forecast = (
    257.4 * 1e6
)  # [TWh -> MWh] TOTAL electricity expected to be supplied to customers during 2024-25 obligation period for GB

# %% [markdown]
# Charging base of RO looks to be total electricity supply - DUKES total electricity supply in 2023 was 247.8 TWh.

# %% [markdown]
# Bill contribution calculation

# %%
ro_levy = ro.ObligationLevel * ro.BuyOutPriceSchemeYear  # [ROC/MWh supplied] * [£/ROC]

# Current levies
levy_var_elec = ro_levy
levy_var_gas = 0
levy_fixed_elec = 0
levy_fixed_gas = 0

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 0
variable_setting = 1

# Supply volumes - DATA ARGUMENT
supply_elec = total_elec_2023
supply_gas = total_gas_2023

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = 0
elec_weight = 1
# gas_weight = supply_gas / (supply_gas + supply_elec) # gas share of supply
# elec_weight = supply_elec / (supply_gas + supply_elec) # elec share of supply
tax_weight = 0

# Assume all domestic electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT (Tentative value)
customers_elec = total_meters_2022_elec
customers_gas = total_meters_2022_gas

# Total target revenue
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %% [markdown]
# ----

# %% [markdown]
# **WHD**

# %%
whd_data = pd.read_parquet(f"{data_root}{date}_WHD_data_tidy.parquet")
current_row = whd_data.index[whd_data["UpdateDate"] == "February 2024"][0]
whd = whd_data.iloc[current_row, :]
whd

# %%
whd_levy = (
    whd.TargetSpendingForSchemeYear / whd.ObligatedSuppliersCustomerBase
)  # [£] / [Customers]
whd_levy  # [£/customer]

# %% [markdown]
# ObligatedSuppliersCustomerBase is "Number of customer of obligated suppliers at 31 December of the previous calendar year" - Ofgem collects this information from suppliers
# - From leglisation: " a relevant supplier's number of domestic customers is number of domestic customers to whom the supplier supplies electricity (other than as part of supply of dual fuel), gas, or dual fuel.
# - From legislation: "a supply of dual fuel to a domestic customer is to be treated as **a supply to two customers**"
# - ObligatedSupplierCustomerBase = elec_only_customers + gas_only_customers + elec_dual_customers + gas_dual_customers
#     - where elec_dual_customers = gas_dual customers

# %%
# Checking number of customers of obligated suppliers
print(f"WHD Customer Base: {whd.ObligatedSuppliersCustomerBase/1e6} million")
print(
    f"Subnational consumption - total number of meters: {(total_meters_2022_elec + total_meters_2022_gas)/1e6} million"
)
print(
    f"Subnational consumption - total number of DOMESTIC meters: {(domestic_meters_2022_elec + domestic_meters_2022_gas)/1e6} million"
)
print(
    f"WHD customer base / total number of domestic meters: {(whd.ObligatedSuppliersCustomerBase/(domestic_meters_2022_elec + domestic_meters_2022_gas))*100} %"
)

# %% [markdown]
# Charging base of WHD looks to be (obligated portion?) domestic meters (gas and electricity)

# %% [markdown]
# **ASSUMPTION CHECK** Assume the same proportion duel fuel:electricity only in WHD customer base as in subnational consumption data for domestic meters (2022-23):

# %%
elec_customer_share_domestic = domestic_meters_2022_elec / (
    domestic_meters_2022_elec + domestic_meters_2022_gas
)
gas_customer_share_domestic = domestic_meters_2022_gas / (
    domestic_meters_2022_elec + domestic_meters_2022_gas
)

print(f"{elec_customer_share_domestic*100} %, {gas_customer_share_domestic*100} %")

# %%
# Target revenue
whd_revenue = whd.TargetSpendingForSchemeYear  # [£]

# Apply above assumption to split of electricity and gas customers in the Obligated Supplier Customer Base
whd_elec_customers = whd.ObligatedSuppliersCustomerBase * elec_customer_share_domestic
whd_gas_customers = whd.ObligatedSuppliersCustomerBase * gas_customer_share_domestic

# Revenue equality check
whd_levy_gas = whd_levy
whd_levy_elec = whd_levy
whd_levy_gas * whd_gas_customers + whd_levy_elec * whd_elec_customers, whd_revenue

# %% [markdown]
# Bill contribution calculation

# %%
whd_levy = (
    whd.TargetSpendingForSchemeYear / whd.ObligatedSuppliersCustomerBase
)  # [£] / [Customers]

levy_var_elec = 0
levy_var_gas = 0
levy_fixed_elec = whd_levy
levy_fixed_gas = whd_levy

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 1
variable_setting = 0

# Supply volumes - DATA ARGUMENT
supply_elec = domestic_elec_2023
supply_gas = domestic_gas_2023

# Apply above assumption to split of electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT
customers_gas = whd.ObligatedSuppliersCustomerBase * gas_customer_share_domestic
customers_elec = whd.ObligatedSuppliersCustomerBase * elec_customer_share_domestic

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = customers_gas / (customers_gas + customers_elec)
elec_weight = customers_elec / (customers_gas + customers_elec)
tax_weight = 0

# Total target revenue (also given in whd.TargetSpendingForSchemeYear)
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %% [markdown]
# ---

# %% [markdown]
# **ECO**

# %%
eco_data = pd.read_parquet(f"{data_root}{date}_ECO_data_tidy.parquet")
current_row = eco_data.index[eco_data["UpdateDate"] == "February 2024"][0]
eco = eco_data.iloc[current_row, :]
eco

# %%
(eco.ObligatedSupplierVolumeGas / domestic_gas_2023), (
    eco.ObligatedSupplierVolumeElectricity / domestic_elec_2023
),

# %% [markdown]
# Charging base of ECO looks to be (obligated portion) of total gas and electricity supply

# %% [markdown]
# Bill contribution calculation

# %%
eco_gas_revenue = (
    eco.AnnualisedCostECO4Gas * (1 + (eco.GDPDeflatorToCurrentPricesECO4 / 100))
) + (
    eco.AnnualisedCostGBISGas * (1 + (eco.GDPDeflatorToCurrentPricesGBIS / 100))
)  # [£]
eco_levy_gas = eco_gas_revenue / eco.ObligatedSupplierVolumeGas  # [£] / [MWh supplied]

eco_elec_revenue = (
    eco.AnnualisedCostECO4Electricity * (1 + (eco.GDPDeflatorToCurrentPricesECO4 / 100))
) + (
    eco.AnnualisedCostGBISElectricity * (1 + (eco.GDPDeflatorToCurrentPricesGBIS / 100))
)  # [£]
eco_levy_elec = (
    eco_elec_revenue / eco.ObligatedSupplierVolumeElectricity
)  # [£] / [MWh supplied]

# %%
eco_levy_gas, eco_levy_elec  # £/MWh supplied

# %%
levy_var_elec = eco_levy_elec
levy_var_gas = eco_levy_gas
levy_fixed_elec = 0
levy_fixed_gas = 0

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 0
variable_setting = 1

# Supply volumes - DATA ARGUMENT
supply_elec = eco.ObligatedSupplierVolumeElectricity
supply_gas = eco.ObligatedSupplierVolumeGas

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = supply_gas / (supply_gas + supply_elec)  # gas share of supply
elec_weight = supply_elec / (supply_gas + supply_elec)  # electricity share of supply
tax_weight = 0

# Assume all domestic electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT (Tentative value)
customers_elec = domestic_meters_2022_elec
customers_gas = domestic_meters_2022_gas

# Total target revenue
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %% [markdown]
# ---

# %% [markdown]
# **AAHEDC**

# %%
aahedc_data = pd.read_parquet(f"{data_root}{date}_AAHEDC_data_tidy.parquet")
current_aahedc = aahedc_data.iloc[current_row, :]
current_aahedc

# %% [markdown]
# https://www.nationalgrideso.com/industry-information/charging/assistance-areas-high-electricity-distribution-costs-aahedc
# - "AAHEDC Tariff Final 2024-25 pdf" -> **2024//25 forecast demand base of 264.33 TWh**, *Total Scheme Amount £111.40m*, Tariff for 2024/25 is 0.042145 p/kWh

# %%
obligated_supplier_volume_elec_aahedc = 264.33 * 1e6  # [MWh]
obligated_supplier_volume_elec_aahedc / 1e6, total_elec_2023 / 1e6, domestic_elec_2023 / 1e6

# %% [markdown]
# Charging base of AAHEDC looks to be total electricity (obligated portion?) of total electricity supply.

# %% [markdown]
# Bill contribution calculation

# %%
# Calculate current levy
if math.isnan(current_aahedc.TariffCurrentYear) == True:
    aahedc_levy = current_aahedc.TariffPreviousYear * (
        1 + current_aahedc.ForecastAnnualRPIPreviousYear / 100
    )  # [p/kWh] * [-]

else:
    aahedc_levy = current_aahedc.TariffCurrentYear  # [p/kWh]
aahedc_levy = aahedc_levy * 1000 / 100  # conversion to [£/MWh]

# Set current levy values
levy_var_elec = aahedc_levy
levy_var_gas = 0
levy_fixed_elec = 0
levy_fixed_gas = 0

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 0
variable_setting = 1

# Supply volumes - DATA ARGUMENT
supply_elec = obligated_supplier_volume_elec_aahedc
supply_gas = total_gas_2023  # TBD

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = 0
elec_weight = 1
# gas_weight = supply_gas / (supply_gas+supply_elec)
# elec_weight = supply_elec / (supply_gas+supply_elec)
tax_weight = 0

# Assume all electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT (Tentative value)
customers_elec = total_meters_2022_elec
customers_gas = total_meters_2022_gas

# Total target revenue
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %% [markdown]
# ----

# %% [markdown]
# **GGL** - CALCULATIONS TO CONFIRM CHARGING BASE NEED CHECKING

# %%
ggl_data = pd.read_parquet(f"{data_root}{date}_GGL_data_tidy.parquet")
current_ggl = ggl_data.iloc[current_row, :]
current_ggl

# %%
if math.isnan(current_ggl.BackdatedLevyRate) == True:
    ggl_levy = (
        current_ggl.LevyRate * 365 / 100
    )  # conversion from [p/meter/day] to [£/meter]
else:
    ggl_levy = (current_ggl.LevyRate * 365 / 100) + (
        current_ggl.BackdatedLevyRate * 122 / 100
    )  # conversion from [p/meter/day] to [£/meter] and accounting that first scheme year only had 122 days

ggl_levy  # [£/meter]

# %% [markdown]
# https://www.gov.uk/government/publications/green-gas-levy-ggl-rates-and-exemptions/green-gas-levy-ggl-rates-underlying-variables-mutualisation-threshold-and-de-minimis-for-the-2024-2025-financial-year
# - See "Underlying variables" to see breakdown of fund costs
# - "The GGL will be charged to fossil fuel gas suppliers for the duration of the GGSS. It is set to fund the full costs of the scheme, including all payments to participants, administration costs, and to cover overspend and under-collection risks."
#
# https://www.legislation.gov.uk/uksi/2021/1335/regulation/39/made<br>
# https://www.legislation.gov.uk/ukdsi/2021/9780348227284/pdfs/ukdsi_9780348227284_en.pdf
# - Calculation and publication of the levy rate

# %%
# Underlying variables from DESNZ
SB = 54_615_635  # £
SD = 9_633_383  # £
AA = 3_460_000  # £
TY = 557_274  # £
TD = -50_182_660  # £
QL = 9_430_870  # £
H = 1_448_709  # £
I = 424  # £
Ofgem_admin = 11_393  # £

ggl_levy_size = SB + AA + TY + TD + QL + H + I - SD + Ofgem_admin  # £
print(f"{ggl_levy_size / 1e6} million £")

# %% [markdown]
# https://www.gov.uk/government/publications/green-gas-levy-ggl-rates-and-exemptions/green-gas-levy-ggl-maximum-collection-amount
# - Maximum collection amount (max amount that can be collected by the levy in any one scheme year)
#     - Current max is £265,988,761 (2037-38; expected peak year)

# %%
# Number of meter points - back-calculate using legislation formula
A = 1.00752

meter_points_ggl = ggl_levy_size / (A * ggl_levy)  # [£] / [£/meter]

meter_points_ggl / 1e6

# %% [markdown]
# According to legislation: M is total number of meter points in the market - i.e. total number of gas meters.

# %%
meter_points_ggl / 1e6, total_meters_2022_gas / 1e6

# %% [markdown]
# Checking values for previous year (2023-24):
# - https://www.gov.uk/government/publications/green-gas-levy-ggl-rates-and-exemptions/green-gas-levy-ggl-rates-underlying-variables-mutualisation-threshold-for-the-2023-2024-financial-year

# %%
## 2023-24
ggl_levy_2023 = 0.45  # £/meter
# Underlying variables from DESNZ
A = 1.00653
SB = 37_832_570  # £
SD = 46_822_210  # £
AA = 3_080_000  # £
TY = 0  # £
TD = 0  # £
QL = 15_887_211  # £
H = 1_256_645  # £
I = 0  # £
Ofgem_admin = 12_500  # £

ggl_levy_size_2023 = SB + AA + TY + TD + QL + H + I - SD + Ofgem_admin  # £
print(f"{ggl_levy_size_2023 / 1e6} million £")

meter_points_ggl_2023 = ggl_levy_size_2023 / (A * ggl_levy_2023)  # [£] / [£/meter]

meter_points_ggl_2023 / 1e6, total_meters_2022_gas / 1e6

# %% [markdown]
# The charging base of AAHEDC looks to be total gas meters.

# %% [markdown]
# Bill contribution calculation

# %%
# Calculate current levy rate
if math.isnan(current_ggl.BackdatedLevyRate) == True:
    ggl_levy = (
        current_ggl.LevyRate * 365 / 100
    )  # conversion from [p/meter/day] to [£/meter]
else:
    ggl_levy = (current_ggl.LevyRate * 365 / 100) + (
        current_ggl.BackdatedLevyRate * 122 / 100
    )  # conversion from [p/meter/day] to [£/meter] and accounting that first scheme year only had 122 days

# Set current levy rates
levy_var_elec = 0
levy_var_gas = 0
levy_fixed_elec = 0
levy_fixed_gas = ggl_levy

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 1
variable_setting = 0

# Supply volumes - DATA ARGUMENT
supply_elec = total_elec_2023
supply_gas = total_gas_2023

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = 1
elec_weight = 0
tax_weight = 0

# Assume all domestic electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT (Tentative value)
customers_elec = total_meters_2022_elec
customers_gas = total_meters_2022_gas

# Total target revenue
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %% [markdown]
# ---

# %% [markdown]
# **FIT**

# %%
fit_data = pd.read_parquet(f"{data_root}{date}_FIT_data_tidy.parquet")
current_row = fit_data.index[
    fit_data["ChargeRestrictionPeriod2"] == "April 2024 - June 2024"
][0]
fit = fit_data.iloc[current_row, :]
fit

# %% [markdown]
# Charging base of FiT is (obligated portion of) total electricity supply.

# %%
(
    fit.TotalElectricitySupplied - fit.ExemptSupplyOutsideUK - fit.ExemptSupplyEII
) / 1e6, total_elec_2023 / 1e6

# %% [markdown]
# Bill contribution calculation

# %%
# Calculate current levy rate
fit_levy = fit.InflatedLevelisationFund / (
    fit.TotalElectricitySupplied - fit.ExemptSupplyOutsideUK - fit.ExemptSupplyEII
)  # [£] / [MWh]

# Set current levy rates
levy_var_elec = fit_levy
levy_var_gas = 0
levy_fixed_elec = 0
levy_fixed_gas = 0

# Fixed or variable mode - SCENARIO ARGUMENT
fixed_setting = 0
variable_setting = 1

# Supply volumes - DATA ARGUMENT
supply_elec = (
    fit.TotalElectricitySupplied - fit.ExemptSupplyOutsideUK - fit.ExemptSupplyEII
)
supply_gas = total_gas_2023

# Revenue weightings - SCENARIO ARGUMENT
gas_weight = 0
elec_weight = 1
tax_weight = 0

# Assume all domestic electricity and gas customers in the Obligated Supplier Customer Base - DATA ARGUMENT (Tentative value)
customers_elec = total_meters_2022_elec
customers_gas = total_meters_2022_gas

# Total target revenue
target_revenue = (
    (levy_var_elec * supply_elec)
    + (levy_var_gas * supply_gas)
    + (levy_fixed_elec * customers_elec)
    + (levy_fixed_gas * customers_gas)
)

# Current bill
bill_current = (
    (levy_var_elec * (tcv.ElectricitySingleRatekWh / 1e3))
    + (levy_var_gas * (tcv.GaskWh / 1e3))
    + levy_fixed_elec
    + levy_fixed_gas
)

calculate_policy_cost_contribution(
    fixed_setting,
    variable_setting,
    gas_weight,
    elec_weight,
    tax_weight,
    supply_elec,
    supply_gas,
    customers_elec,
    customers_gas,
    target_revenue,
    bill_current,
)

# %%
