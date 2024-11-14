from tariffs import (
    ElectricityOtherPayment,
    GasOtherPayment,
    ElectricityPPM,
    GasPPM,
    ElectricityStandardCredit,
    GasStandardCredit,
)


def get_preset_weights(preset_name, customers_elec, customers_gas):
    # Default values for all presets
    default_shares = {
        "ro": 0,
        "aahedc": 0,
        "ggl": 0,
        "whd": 0,
        "eco": 0,
        "fit": 0,
    }

    levy_elec_shares = default_shares.copy()
    levy_gas_shares = default_shares.copy()
    levy_fixed_shares = default_shares.copy()

    # Common values for "All gas" and "All electricity" presets
    if preset_name in [
        "All gas, status quo fixed or variable",
        "All electricity, status quo fixed or variable",
    ]:
        if "gas" in preset_name:
            levy_gas_shares = {key: 100 for key in default_shares}
        else:
            levy_elec_shares = {key: 100 for key in default_shares}
        levy_fixed_shares = {
            "ro": 0,
            "aahedc": 0,
            "ggl": 100,
            "whd": 100,
            "eco": 0,
            "fit": 0,
        }

    # Presets based on gas and electricity shares
    elif preset_name in [
        "Status quo gas and electricity, all fixed",
        "Status quo gas and electricity, all variable",
    ]:
        common_levy_gas = {
            "ro": 0,
            "aahedc": 0,
            "ggl": 100,
            "whd": round((customers_gas / (customers_elec + customers_gas)) * 100),
            "eco": 50,
            "fit": 0,
        }
        common_levy_elec = {
            "ro": 100,
            "aahedc": 100,
            "ggl": 0,
            "whd": round((customers_elec / (customers_elec + customers_gas)) * 100),
            "eco": 50,
            "fit": 100,
        }

        levy_gas_shares.update(common_levy_gas)
        levy_elec_shares.update(common_levy_elec)

        if "fixed" in preset_name:
            levy_fixed_shares = {key: 100 for key in default_shares}
        else:
            levy_fixed_shares = default_shares

    # Preset for pure status quo
    elif preset_name == "Status quo":
        levy_gas_shares = {
            "ro": 0,
            "aahedc": 0,
            "ggl": 100,
            "whd": round((customers_gas / (customers_elec + customers_gas)) * 100),
            "eco": 50,
            "fit": 0,
        }
        levy_elec_shares = {
            "ro": 100,
            "aahedc": 100,
            "ggl": 0,
            "whd": round((customers_elec / (customers_elec + customers_gas)) * 100),
            "eco": 50,
            "fit": 100,
        }
        levy_fixed_shares = {
            "ro": 0,
            "aahedc": 0,
            "ggl": 100,
            "whd": 100,
            "eco": 0,
            "fit": 0,
        }

    return levy_elec_shares, levy_gas_shares, levy_fixed_shares


def get_bills(tariff_payment_method, scenario_name, elec_data, gas_data):
    if tariff_payment_method == "Other payment method":
        elec_class = ElectricityOtherPayment
        gas_class = GasOtherPayment
        elec_nil, elec_typical = elec_data["other_payment"]
        gas_nil, gas_typical = gas_data["other_payment"]

    elif tariff_payment_method == "Prepayment meter":
        elec_class = ElectricityPPM
        gas_class = GasPPM
        elec_nil, elec_typical = elec_data["ppm"]
        gas_nil, gas_typical = gas_data["ppm"]

    elif tariff_payment_method == "Standard Credit":
        elec_class = ElectricityStandardCredit
        gas_class = GasStandardCredit
        elec_nil, elec_typical = elec_data["standard_credit"]
        gas_nil, gas_typical = gas_data["standard_credit"]

    else:
        raise ValueError("Unknown tariff payment method")

    elec_bills = {
        "baseline": elec_class.from_dataframe(elec_nil, elec_typical),
        scenario_name: elec_class.from_dataframe(elec_nil, elec_typical),
    }
    gas_bills = {
        "baseline": gas_class.from_dataframe(gas_nil, gas_typical),
        scenario_name: gas_class.from_dataframe(gas_nil, gas_typical),
    }

    return elec_bills, gas_bills
