# %%
import pandas as pd

from datetime import datetime

from asf_levies_model import PROJECT_DIR

import asf_levies_model.getters.load_data as data
import asf_levies_model.levies as levies
import asf_levies_model.tariffs as tariffs

# %%
"""
Setting up Levies and LevyCollection
"""

# %%
# Get Annex 4
fileobject = data.download_annex_4(as_fileobject=True)

# %%
# Denominator values from Desnz subnational consumption domestic data, 2023
supply_elec = 96_517_461
supply_gas = 266_505_188
customers_gas = 24_605_467
customers_elec = 29_239_936

denominator_values = {
    "supply_elec": supply_elec,
    "supply_gas": supply_gas,
    "customers_gas": customers_gas,
    "customers_elec": customers_elec,
}

# %%
# Scaling factor for estimating domestic share of FIT revenue
total_supply_elec = (
    249_044_438  # DESNZ GB total electricity consumption - all meters (2023)
)
unscaled_fit = levies.FIT.from_dataframe(
    data.process_data_FIT(fileobject),
)
exempt_eii_supply = unscaled_fit.ExemptSupplyEII
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %%
# Scaling factor for estimating domestic share of NCC revenue
unscaled_ncc = levies.NCC.from_dataframe(
    data.process_data_NCC(fileobject),
)
ncc_eligible_supply = unscaled_ncc.EligibleDemand
ncc_scaling_factor = supply_elec / ncc_eligible_supply

# %%
# Instantiate LevyCollection with scaled levies

list_levies = [
    levies.RO.from_dataframe(data.process_data_RO(fileobject), denominator=supply_elec),
    levies.AAHEDC.from_dataframe(
        data.process_data_AAHEDC(fileobject), denominator=supply_elec
    ),
    levies.GGL.from_dataframe(
        data.process_data_GGL(fileobject), denominator=customers_gas
    ),
    levies.WHD.from_dataframe(
        data.process_data_WHD(fileobject),
        customers_gas=customers_gas,
        customers_elec=customers_elec,
    ),
    levies.ECO4.from_dataframe(data.process_data_ECO(fileobject)),  # Split ECO
    levies.GBIS.from_dataframe(data.process_data_ECO(fileobject)),  # Split ECO
    levies.FIT.from_dataframe(
        data.process_data_FIT(fileobject),
        scaling_factor=fit_scaling_factor,
    ),
    levies.NCC.from_dataframe(
        data.process_data_NCC(fileobject), scaling_factor=ncc_scaling_factor
    ),
]


pc = levies.LevyCollection("Policy Costs", "pc", list_levies, denominator_values)

# Rebalance to denominators
pc = pc.rebalance_to_denominators()

# %%
"""
Setting up Tariffs
"""

# %%
# Get Annex 9
fileobject = data.download_annex_9(as_fileobject=True)

# %%
# Other Payment Method Tariffs
other_gas_tariff = tariffs.GasOtherPayment.from_dataframe(
    data.process_tariff_gas_other_payment_nil(fileobject),
    data.process_tariff_gas_other_payment_typical(fileobject),
)
other_electricity_tariff = tariffs.ElectricityOtherPayment.from_dataframe(
    data.process_tariff_elec_other_payment_nil(fileobject),
    data.process_tariff_elec_other_payment_typical(fileobject),
)


# Update policy costs with denominator rebalanced policy costs
other_gas_tariff = other_gas_tariff.update_policy_costs(pc)
other_electricity_tariff = other_electricity_tariff.update_policy_costs(pc)

# Check values
other_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + other_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %%
# Standard Credit Tariffs
credit_gas_tariff = tariffs.GasStandardCredit.from_dataframe(
    data.process_tariff_gas_standard_credit_nil(fileobject),
    data.process_tariff_gas_standard_credit_typical(fileobject),
)
credit_electricity_tariff = tariffs.ElectricityStandardCredit.from_dataframe(
    data.process_tariff_elec_standard_credit_nil(fileobject),
    data.process_tariff_elec_standard_credit_typical(fileobject),
)


# Update policy costs with denominator rebalanced policy costs
credit_gas_tariff = credit_gas_tariff.update_policy_costs(pc)
credit_electricity_tariff = credit_electricity_tariff.update_policy_costs(pc)

# Check values
credit_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + credit_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %%
# PPM Tariffs
ppm_gas_tariff = tariffs.GasPPM.from_dataframe(
    data.process_tariff_gas_ppm_nil(fileobject),
    data.process_tariff_gas_ppm_typical(fileobject),
)
ppm_electricity_tariff = tariffs.ElectricityPPM.from_dataframe(
    data.process_tariff_elec_ppm_nil(fileobject),
    data.process_tariff_elec_ppm_typical(fileobject),
)


# Update policy costs with denominator rebalanced policy costs
ppm_gas_tariff = ppm_gas_tariff.update_policy_costs(pc)
ppm_electricity_tariff = ppm_electricity_tariff.update_policy_costs(pc)

# Check values
ppm_gas_tariff.calculate_total_consumption(
    11.5, vat=True
) + ppm_electricity_tariff.calculate_total_consumption(2.7, vat=True)

# %%
fileobject.close()
