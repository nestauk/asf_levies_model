import copy
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, Union, Dict, List, Tuple
import warnings

from asf_levies_model.utils.utils import (
    _generate_docstring,
    PriceCapPeriod,
    _dictionary_depth,
)


class Levy:
    """A generic levy object for gas and electricity policy costs and rebalancing.

        Intended primarily as a parent class for specific levies, but can be used as
    a general levy object for prototyping.

        It is expected that:
            electricity_weight + gas_weight + tax_weight = 1
            electricity_variable_weight + electricity_fixed_weight = 1 if electricity_weight > 0
            gas_variable_weight + gas_fixed_weight = 1 if gas_weight > 0

        Attributes:
            name: String giving the full name of a levy.
            short_name: String giving an abbreviated name for a levy.
            electricity_weight: float [0, 1] indicating electricity proportion of levy revenue.
            gas_weight: float [0, 1] indicating gas proportion of levy revenue.
            tax_weight: float [0, 1] indicating general taxation proportion of levy revenue.
            electricity_variable_weight: float [0, 1] indicating the proportion of electricity revenue that is variable (e.g. per unit consumption).
            electricity_fixed_weight: float [0, 1] indicating the proportion of electricity revenue that is fixed (e.g. per customer).
            gas_variable_weight: float [0, 1] indicating the proportion of gas revenue that is variable (e.g. per unit consumption).
            gas_fixed_weight: float [0, 1] indicating the proportion of gas revenue that is fixed (e.g. per customer).
            electricity_variable_rate: float [0, inf) the electricity variable rate for a levy.
            electricity_fixed_rate: float [0, inf) the electricity fixed rate for a levy.
            gas_variable_rate: float [0, inf) the gas variable rate for a levy.
            gas_fixed_rate: float [0, inf) the gas fixed rate for a levy.
            general_taxation: float [0, inf) the levy revenue passed to general taxation.
            revenue: float [0, inf) the total levy revenue.
            price_cap_period: Interval indicating the price cap period the levy covers.
    """

    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        """Initializes the instance based on provided levy parameters.

        Args:
            name: Full name of levy instance.
            short_name: Abbreviated name/initialisation of levy instance.
            electricity_weight: Proportion of levy charged to electricity bills.
            gas_weight: Proportion of levy charged to gas bills.
            tax_weight: Proportion of levy abstracted to general taxation.
            electricity_variable_weight: Share of levy charged variably against electricity consumption (proportion).
            electricity_fixed_weight: Share of levy that is a fixed charge against electricity customers (proportion).
            gas_variable_weight: Share of levy charged variably against gas consumption (proportion).
            gas_fixed_weight: Share of levy that is a fixed charge against gas customers (proportion).
            electricity_variable_rate: Rate to calculate electricity variable cost (per MWh).
            electricity_fixed_rate: Rate to calculate electricity fixed cost (per customer or meter).
            gas_variable_rate: Rate to calculate gas variable cost (per MWh).
            gas_fixed_rate: Rate to calculate gas fixed cost (per customer or meter).
            general_taxation: Revenue abstracted to general taxation (absolute value).
            revenue: Total levy revenue (absolute value).
            price_cap_period: Energy price cap period covered by the levy instance.
        """
        self.name = name
        self.short_name = short_name

        # Mode split
        self.electricity_weight = electricity_weight
        self.gas_weight = gas_weight
        self.tax_weight = tax_weight

        # Method of levying
        self.electricity_variable_weight = electricity_variable_weight
        self.electricity_fixed_weight = electricity_fixed_weight
        self.gas_variable_weight = gas_variable_weight
        self.gas_fixed_weight = gas_fixed_weight

        # levy rate
        self.electricity_variable_rate = electricity_variable_rate
        self.electricity_fixed_rate = electricity_fixed_rate
        self.gas_variable_rate = gas_variable_rate
        self.gas_fixed_rate = gas_fixed_rate
        self.general_taxation = general_taxation

        # revenue
        self.revenue = revenue

        # price cap period
        self.price_cap_period = price_cap_period

    def calculate_levy(
        self,
        electricity_consumption: float,
        gas_consumption: float,
        electricity_customer: bool,
        gas_customer: bool,
    ) -> float:
        """Calculate total levy amount (variable + fixed costs) for given consumer profile.

        Args:
            electricity_consumption: float [0, inf), electricity consumption in MWh.
            gas_consumption: float [0, inf), gas consumption in MWh.
            electricity_customer: bool, whether electricity customer.
            gas_customer: bool, whether gas customer.
        """
        return self.calculate_variable_levy(
            electricity_consumption, gas_consumption
        ) + self.calculate_fixed_levy(electricity_customer, gas_customer)

    def calculate_variable_levy(
        self, electricity_consumption: float, gas_consumption: float
    ) -> float:
        """Calculate variable component of levy for given consumption.

        Args:
            electricity_consumption: float [0, inf), electricity consumption in MWh.
            gas_consumption: float [0, inf), gas consumption in MWh.
        """
        return (
            self.electricity_variable_rate * electricity_consumption
            + self.gas_variable_rate * gas_consumption
        )

    def calculate_fixed_levy(
        self, electricity_customer: bool, gas_customer: bool
    ) -> float:
        """Calculate fixed component of levy for given customers.

        Args:
            electricity_customer: bool, whether electricity customer.
            gas_customer: bool, whether gas customer.
        """
        return (self.electricity_fixed_rate * electricity_customer) + (
            self.gas_fixed_rate * gas_customer
        )

    def update_revenue(
        self,
        new_revenue: float,
        supply_gas: float,
        supply_elec: float,
        customers_gas: int,
        customers_elec: int,
        overwrite: bool = True,
        inplace: bool = False,
    ) -> Optional["Levy"]:
        """Update the levy revenue.

                The default (overwrite = True) sets a new_revenue as revenue and updates the levy rate using
        the provided denominators.

                If overwrite is set to False, the revenue is modified by new_revenue, a positive value
        increases revenue (i.e. revenue = revenue + new_revenue), while a negative value decreases revenue
        (i.e. revenue = revenue - new_revenue).

                Args:
                    new_revenue: float (-inf, inf), new revenue to update existing levy revenue.
                    supply_gas: float [0, inf) annual gas supply value (MWh).
                    supply_elec: float [0, inf) annual electricity supply value (MWh)
                    customers_gas: int [0, inf) annual gas customers (customer or meter count).
                    customers_elec: int [0, inf) annual electricity customers (customer or meter count).
                    overwrite: bool (default: True): whether to overwrite existing revenue with new_revenue or modify by new_revenue.
                    inplace: bool (default: False): whether to update levy instance inplace or return new levy instance.
        """
        if overwrite & (new_revenue < 0):
            raise ValueError(
                "Cannot set revenue to negative value. To update revenue set overwrite to False."
            )

        if (not overwrite) & ((self.revenue + new_revenue) < 0):
            raise ValueError("Updated revenue cannot be negative.")

        # 1. Update revenue
        if overwrite:
            revenue = new_revenue
        elif not overwrite:
            revenue = self.revenue + new_revenue
        else:
            raise AttributeError("Error in assigning new revenue to Levy.")

        # 2. Update levy rate
        # Revenue contributions
        revenue_gas = revenue * self.gas_weight
        revenue_elec = revenue * self.electricity_weight
        revenue_tax = revenue * self.tax_weight
        # New variable levy rate
        new_levy_var_gas = (revenue_gas / supply_gas) * self.gas_variable_weight
        new_levy_var_elec = (
            revenue_elec / supply_elec
        ) * self.electricity_variable_weight
        # New fixed levy rate
        new_levy_fixed_gas = (revenue_gas / customers_gas) * self.gas_fixed_weight
        new_levy_fixed_elec = (
            revenue_elec / customers_elec
        ) * self.electricity_fixed_weight

        if inplace:
            # Update revenue
            self.revenue = revenue
            self.electricity_variable_rate = new_levy_var_elec
            self.electricity_fixed_rate = new_levy_fixed_elec
            self.gas_variable_rate = new_levy_var_gas
            self.gas_fixed_rate = new_levy_fixed_gas
            self.general_taxation = revenue_tax
        else:
            # Return copy
            new_levy = copy.deepcopy(self)
            new_levy.revenue = revenue
            new_levy.electricity_variable_rate = new_levy_var_elec
            new_levy.electricity_fixed_rate = new_levy_fixed_elec
            new_levy.gas_variable_rate = new_levy_var_gas
            new_levy.gas_fixed_rate = new_levy_fixed_gas
            new_levy.general_taxation = revenue_tax
            return new_levy

    def rebalance_levy(
        self,
        new_electricity_weight: float,
        new_gas_weight: float,
        new_tax_weight: float,
        new_variable_weight_elec: float,
        new_fixed_weight_elec: float,
        new_variable_weight_gas: float,
        new_fixed_weight_gas: float,
        supply_gas: float,
        supply_elec: float,
        customers_gas: int,
        customers_elec: int,
        inplace: bool = False,
    ) -> Optional["Levy"]:
        """Rebalance levy based on inputs.

                Rebalancing is revenue-based, reapportioning revenue using the provided parameters and deriving
        rates from the provided supply values or customer numbers.

                It is expected that:
                    new_electricity_weight + new_gas_weight + new_tax_weight = 1
                    new_variable_weight_elec + new_fixed_weight_elec = 1 if new_electricity_weight > 0
                    new_variable_weight_gas + new_fixed_weight_gas = 1 if new_gas_weight > 0

                Args
                    new_electricity_weight: float [0, 1] new proportion of levy revenue to be charged to electricity.
                    new_gas_weight: float [0, 1] new proportion of levy revenue to be charged to gas.
                    new_tax_weight: float [0, 1] new proportion of levy revenue to be charged to general taxation.
                    new_variable_weight_elec: float [0, 1] new proportion of levy electricity revenue to charge based on consumption.
                    new_fixed_weight_elec: float [0, 1] new proportion of levy electricity revenue to charge based on customer numbers.
                    new_variable_weight_gas: float [0, 1] new proportion of levy gas revenue to charge based on consumption.
                    new_fixed_weight_gas: float [0, 1] new proportion of levy gas revenue to charge based on customer numbers.
                    supply_gas: float [0, inf) annual gas supply value (MWh).
                    supply_elec: float [0, inf) annual electricity supply value (MWh)
                    customers_gas: int [0, inf) annual gas customers (customer or meter count).
                    customers_elec: int [0, inf) annual electricity customers (customer or meter count).
                    inplace: bool (default: False): whether to update levy instance inplace or return new levy instance.

                Raises:
                    ValueError: if rebalancing fails to maintain total revenue.
        """

        # Revenue contributions
        revenue_gas = self.revenue * new_gas_weight
        revenue_elec = self.revenue * new_electricity_weight
        revenue_tax = self.revenue * new_tax_weight

        # New variable levy rate
        new_levy_var_gas = (revenue_gas / supply_gas) * new_variable_weight_gas
        new_levy_var_elec = (revenue_elec / supply_elec) * new_variable_weight_elec

        # New fixed levy rate
        new_levy_fixed_gas = (revenue_gas / customers_gas) * new_fixed_weight_gas
        new_levy_fixed_elec = (revenue_elec / customers_elec) * new_fixed_weight_elec

        if not self._is_revenue_maintained(
            new_levy_var_gas,
            new_levy_var_elec,
            new_levy_fixed_gas,
            new_levy_fixed_elec,
            supply_gas,
            supply_elec,
            customers_gas,
            customers_elec,
            revenue_tax,
            self.revenue,
        ):
            raise ValueError(
                "Rebalancing failed to maintain revenue. (Try: Check that new electricity-gas-tax and fixed-variable weights provided add up to 1, respectively.)"
            )

        if inplace:
            # Update attributes
            self.electricity_weight = new_electricity_weight
            self.gas_weight = new_gas_weight
            self.tax_weight = new_tax_weight

            self.electricity_variable_weight = new_variable_weight_elec
            self.electricity_fixed_weight = new_fixed_weight_elec
            self.gas_variable_weight = new_variable_weight_gas
            self.gas_fixed_weight = new_fixed_weight_gas

            self.electricity_variable_rate = new_levy_var_elec
            self.electricity_fixed_rate = new_levy_fixed_elec
            self.gas_variable_rate = new_levy_var_gas
            self.gas_fixed_rate = new_levy_fixed_gas
            self.general_taxation = revenue_tax
        else:
            # Return copy
            new_levy = copy.deepcopy(self)
            # Update attributes
            new_levy.electricity_weight = new_electricity_weight
            new_levy.gas_weight = new_gas_weight
            new_levy.tax_weight = new_tax_weight

            new_levy.electricity_variable_weight = new_variable_weight_elec
            new_levy.electricity_fixed_weight = new_fixed_weight_elec
            new_levy.gas_variable_weight = new_variable_weight_gas
            new_levy.gas_fixed_weight = new_fixed_weight_gas

            new_levy.electricity_variable_rate = new_levy_var_elec
            new_levy.electricity_fixed_rate = new_levy_fixed_elec
            new_levy.gas_variable_rate = new_levy_var_gas
            new_levy.gas_fixed_rate = new_levy_fixed_gas
            new_levy.general_taxation = revenue_tax
            return new_levy

    @staticmethod
    def _is_revenue_maintained(
        new_levy_var_gas: float,
        new_levy_var_elec: float,
        new_levy_fixed_gas: float,
        new_levy_fixed_elec: float,
        supply_gas: float,
        supply_elec: float,
        customers_gas: int,
        customers_elec: int,
        tax_revenue: float,
        target_revenue: float,
    ) -> bool:
        """Checks that revenue is maintained for rebalancing."""
        new_revenue_gas = (new_levy_var_gas * supply_gas) + (
            new_levy_fixed_gas * customers_gas
        )
        new_revenue_elec = (new_levy_var_elec * supply_elec) + (
            new_levy_fixed_elec * customers_elec
        )

        if (
            abs((new_revenue_gas + new_revenue_elec + tax_revenue) - target_revenue)
            < 0.01
        ):
            return True
        else:
            return False

    def __repr__(self):
        """Printable representation of levy instance."""
        non_zero = [
            attr
            for attr in [
                "electricity_weight",
                "gas_weight",
                "tax_weight",
                "electricity_variable_weight",
                "electricity_fixed_weight",
                "gas_variable_weight",
                "gas_fixed_weight",
                "electricity_variable_rate",
                "electricity_fixed_rate",
                "gas_variable_rate",
                "gas_fixed_rate",
                "general_taxation",
            ]
            if getattr(self, attr) > 0
        ]

        return repr(
            f'Levy(name="{self.name}", short_name="{self.short_name}", price_cap_period="{repr(self.price_cap_period)}", {", ".join([f"{attr}={getattr(self, attr)}" for attr in non_zero])})'
        )

    def __str__(self):
        """Simple string representation of levy instance."""
        return str(f'Levy(name="{self.name}", short_name="{self.short_name}")')


class RO(Levy):
    """Renewables Obligation Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        obligation_level: float, obligation level for scheme year (ROCS/MWh supplied).
        BuyOutPriceSchemeYear: float, final buy-out price for scheme year (£/ROC).
        BuyOutPricePreviousYear: float, final buy-out price for previous scheme year (£/ROC).
        ForecastAnnualRPIPreviousYear: float, forecast of annual RPI for previous calendar year (%).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            obligation_level: required number of ROCs per MWh supplied for scheme year.",
            "            BuyOutPriceSchemeYear: final buy out price (£ per ROC) for scheme year.",
            "            BuyOutPricePreviousYear: final buy out price (£ per ROC) for previous scheme year.",
            "            ForecastAnnualRPIPreviousYear: RPI (inflation) forecast for previous calendar year.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        obligation_level: float,
        BuyOutPriceSchemeYear: float,
        BuyOutPricePreviousYear: float,
        ForecastAnnualRPIPreviousYear: float,
    ) -> None:
        super(RO, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.obligation_level = obligation_level
        self.BuyOutPriceSchemeYear = BuyOutPriceSchemeYear
        self.BuyOutPricePreviousYear = BuyOutPricePreviousYear
        self.ForecastAnnualRPIPreviousYear = ForecastAnnualRPIPreviousYear

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        denominator: float = None,
        price_cap: str = "LATEST",
    ) -> "RO":
        """Create RO levy instance from dataframe input.

        Uses the `process_data_RO()` output from `asf_levies_model.getters.load_data` to \
initialise a RO levy object at present values.

        As RO doesn't have a stated revenue or scheme cost, revenue must either be provided, \
or a denominator in MWh given to calculate it from the levy value (£/MWh).

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, obligation_level,\
BuyOutPriceSchemeYear, BuyOutPricePreviousYear, ForecastAnnualRPIPreviousYear fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total supply amount (MWh) to calculate the revenue.
            price_cap: str, price cap period to use; default: LATEST.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df[["ObligationLevel", "BuyOutPriceSchemeYear"]]
                .isna()
                .all(axis=1)
                .to_numpy()
                .nonzero()[0][0]
            )
            df = df.iloc[latest_index - 1]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        ro_levy = cls.calculate_renewable_obligation_rate(
            df.ObligationLevel,
            df.BuyOutPriceSchemeYear,
            df.BuyOutPricePreviousYear,
        )

        if not revenue:
            revenue = ro_levy * denominator

        return cls(
            name="Renewables Obligation",
            short_name="ro",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=0,
            electricity_variable_rate=ro_levy,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            obligation_level=df.ObligationLevel,
            BuyOutPriceSchemeYear=df.BuyOutPriceSchemeYear,
            BuyOutPricePreviousYear=df.BuyOutPricePreviousYear,
            ForecastAnnualRPIPreviousYear=df.ForecastAnnualRPIPreviousYear,
        )

    @staticmethod
    def calculate_renewable_obligation_rate(
        ObligationLevel: float,
        BuyOutPriceSchemeYear: float,
        BuyOutPricePreviousYear: float,
    ) -> float:
        """Calculate renewable obligation rate from component values."""
        return (
            ObligationLevel * BuyOutPriceSchemeYear
            if not np.isnan(BuyOutPriceSchemeYear)
            else ObligationLevel * BuyOutPricePreviousYear
        )


class AAHEDC(Levy):
    """Assistance for Areas with High Electricity Distribution Costs Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        TariffCurrentYear: float, final AAHEDC tariff for current charging year (p/kWh at GSP).
        TariffPreviousYear: float, final AAHEDC tariff for previous charging year (p/kWh at GSP).
        ForecastAnnualRPIPreviousYear: float, forecast of annual RPI for previous calendar year (%).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            TariffCurrentYear: final AAHEDC tariff for current charging year.",
            "            TariffPreviousYear: final AAHEDC tariff for previous charging year.",
            "            ForecastAnnualRPIPreviousYear: RPI (inflation) forecast for previous calendar year.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        TariffCurrentYear: float,
        TariffPreviousYear: float,
        ForecastAnnualRPIPreviousYear: float,
    ) -> None:
        super(AAHEDC, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.TariffCurrentYear = TariffCurrentYear
        self.TariffPreviousYear = TariffPreviousYear
        self.ForecastAnnualRPIPreviousYear = ForecastAnnualRPIPreviousYear

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        denominator: float = None,
        price_cap: str = "LATEST",
    ) -> "AAHEDC":
        """Create AAHEDC levy instance from dataframe input.

        Uses the `process_data_AAHEDC()` output from `asf_levies_model.getters.load_data` to \
initialise an AAHEDC levy object at present values.

        As AAHEDC doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator in MWh given to calculate it from the levy value (£/MWh at GSP).

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, TariffCurrentYear,\
TariffPreviousYear, ForecastAnnualRPIPreviousYear fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total supply amount (MWh) to calculate the revenue.
            price_cap: str, price cap period to use; default: LATEST.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df[["TariffCurrentYear", "TariffPreviousYear"]]
                .isna()
                .all(axis=1)
                .to_numpy()
                .nonzero()[0][0]
            )
            df = df.iloc[latest_index - 1]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        aahedc_tariff_forecast = cls.calculate_aahedc_tariff_forecast(
            df.TariffPreviousYear, df.ForecastAnnualRPIPreviousYear
        )

        aahedc_levy = cls.calculate_aahedc_rate(
            df.TariffCurrentYear, aahedc_tariff_forecast
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = aahedc_levy * denominator

        return cls(
            name="Assistance for Areas with High Electricity Distribution Costs",
            short_name="aahedc",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=0,
            electricity_variable_rate=aahedc_levy,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            TariffCurrentYear=df.TariffCurrentYear,
            TariffPreviousYear=df.TariffPreviousYear,
            ForecastAnnualRPIPreviousYear=df.ForecastAnnualRPIPreviousYear,
        )

    @staticmethod
    def calculate_aahedc_tariff_forecast(
        TariffPreviousYear: float, ForecastAnnualRPIPreviousYear: float
    ) -> float:
        """Calculate AAHEDC tariff forecast from given values."""
        return TariffPreviousYear * (1 + ForecastAnnualRPIPreviousYear / 100)

    @staticmethod
    def calculate_aahedc_rate(
        TariffCurrentYear: float, aahedc_tariff_forecast: float
    ) -> float:
        """Calculate AAHEDC rate from given values."""
        return (
            TariffCurrentYear * 10
            if not np.isnan(TariffCurrentYear)
            else aahedc_tariff_forecast * 10
        )


class GGL(Levy):
    """Green Gas Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        LevyRate: float, levy rate (p/meter/day).
        BackdatedLevyRate: float, backdated levy rate for first scheme year (p/meter/day).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest",
            "            LevyRate: levy rate (p/meter/day)",
            "            BackdatedLevyRate: backdated levy rate for first scheme year (p/meter/day)",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        LevyRate: float,
        BackdatedLevyRate: float,
    ) -> None:
        super(GGL, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.LevyRate = LevyRate
        self.BackdatedLevyRate = BackdatedLevyRate

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        denominator: float = None,
        price_cap: str = "LATEST",
    ) -> "GGL":
        """Create GGL levy instance from dataframe input.

        Uses the `process_data_GGL()` output from `asf_levies_model.getters.load_data` to \
initialise a GGL levy object at present values.

        As GGL doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator (number of meters) given to calculate it from the levy value (£/meter).

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, LevyRate, BackdatedLevyRate fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total number of meters (customers) to calculate the revenue.
            price_cap: str, price cap period to use; default: LATEST.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = df["LevyRate"].notna().to_numpy().nonzero()[0].max()

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        ggl_levy = cls.calculate_ggl_rate(df.LevyRate, df.BackdatedLevyRate)

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = ggl_levy * denominator

        return cls(
            name="Green Gas Levy",
            short_name="ggl",
            electricity_weight=0,
            gas_weight=1,
            tax_weight=0,
            electricity_variable_weight=0,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=1,
            electricity_variable_rate=0,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=ggl_levy,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            LevyRate=df.LevyRate,
            BackdatedLevyRate=df.BackdatedLevyRate,
        )

    @staticmethod
    def calculate_ggl_rate(LevyRate: float, BackdatedLevyRate: float) -> float:
        """Calculate Green Gas Levy rate from given values."""
        return (
            (LevyRate * 365 / 100)
            if np.isnan(BackdatedLevyRate)
            else (LevyRate * 365 / 100) + (BackdatedLevyRate * 122 / 100)
        )


class NCC(Levy):
    """Network Charging Compensation Scheme.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        EstimatedLevyFund: float, total estimated levyfund amount.
        AdminCosts: float, establishing and operating process costs.
        ReserveFund: float, reserve allowance.
        EligibleDemand: float, supply volume domestic and non-domestic, non-EII (MWh).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest",
            "            EstimatedLevyFund: total estimated levyfund amount",
            "            AdminCosts: establishing and operating process costs",
            "            ReserveFund: reserve allowance",
            "            EligibleDemand: supply volume domestic and non-domestic, non-EII (MWh)",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        EstimatedLevyFund: float,
        AdminCosts: float,
        ReserveFund: float,
        EligibleDemand: float,
    ) -> None:
        super(NCC, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.EstimatedLevyFund = EstimatedLevyFund
        self.AdminCosts = AdminCosts
        self.ReserveFund = ReserveFund
        self.EligibleDemand = EligibleDemand

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        scaling_factor: float = 1.0,
        price_cap: str = "LATEST",
    ) -> "NCC":
        """Create NCC levy instance from dataframe input.

        Uses the `process_data_NCC()` output from `asf_levies_model.getters.load_data` to \
initialise an NCC levy object at present values.

        As NCC has a stated levy fund amount, this is used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, LevyRate, BackdatedLevyRate fields.
            revenue: float, a total revenue amount (£) for the levy.
            scaling_factor: float, factor to scale total revenue amount (£) to reflect e.g. only domestic share.
            price_cap: str, price cap period to use; default: LATEST.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = df["EstimatedLevyFund"].notna().to_numpy().nonzero()[0].max()

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        ncc_levy = cls.calculate_ncc_rate(
            df.EstimatedLevyFund, df.AdminCosts, df.ReserveFund, df.EligibleDemand
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = (
                sum([df.EstimatedLevyFund, df.AdminCosts, df.ReserveFund])
                * scaling_factor
            )
        else:
            revenue *= scaling_factor

        return cls(
            name="Network Charging Compensation Scheme",
            short_name="ncc",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=0,
            electricity_variable_rate=ncc_levy,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            EstimatedLevyFund=df.EstimatedLevyFund,
            AdminCosts=df.AdminCosts,
            ReserveFund=df.ReserveFund,
            EligibleDemand=df.EligibleDemand,
        )

    @staticmethod
    def calculate_ncc_rate(
        EstimatedLevyFund: float,
        AdminCosts: float,
        ReserveFund: float,
        EligibleDemand: float,
    ) -> float:
        """Calculate Network Charging Compensation Scheme rate from given values."""
        return sum([EstimatedLevyFund, AdminCosts, ReserveFund]) / EligibleDemand


class WHD(Levy):
    """Warm Homes Discount Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        TargetSpendingForSchemeYear: float, target spending on WHD (GB) for scheme year (£).
        CoreSpending: float, spending that provides discount for core groups 1 and 2 (£).
        NoncoreSpending: float, spending on industry initiatives and broader group rebates (£).
        ObligatedSuppliersCustomerBase: int, number of customers of obligated suppliers (count).
        CompulsorySupplierFractionOfCoreGroup: float, compulsory suppliers percentage of core group (%).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            TargetSpendingForSchemeYear: target spending on WHD (GB) for scheme year.",
            "            CoreSpending: spending on core groups.",
            "            NoncoreSpending: spending on industry initiatives and broader group rebates.",
            "            ObligatedSuppliersCustomerBase: number of customers of obligated suppliers.",
            "            CompulsorySupplierFractionOfCoreGroup: compulsory suppliers percentage of core group.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        TargetSpendingForSchemeYear: float,
        CoreSpending: float,
        NoncoreSpending: float,
        ObligatedSuppliersCustomerBase: int,
        CompulsorySupplierFractionOfCoreGroup: float,
    ) -> None:
        super(WHD, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.TargetSpendingForSchemeYear = TargetSpendingForSchemeYear
        self.CoreSpending = CoreSpending
        self.NoncoreSpending = NoncoreSpending
        self.ObligatedSuppliersCustomerBase = ObligatedSuppliersCustomerBase
        self.CompulsorySupplierFractionOfCoreGroup = (
            CompulsorySupplierFractionOfCoreGroup
        )

    @classmethod
    def from_dataframe(
        cls,
        df,
        revenue=None,
        customers_gas=None,
        customers_elec=None,
        price_cap: str = "LATEST",
    ):
        """Create WHD levy instance from dataframe input.

        Uses the `process_data_WHD()` output from `asf_levies_model.getters.load_data` to \
initialise a WHD levy object at present values.

        As WHD has a stated scheme cost, this is used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        WHD is balanced between gas and electricity customers to produce a single rate, however \
the ofgem spreadsheet doesn't provide sufficient information to calculate the effective gas and electric \
shares. If customers_gas and customers_elec are provided the levy gets share information for the status quo levy.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, TargetSpendingForSchemeYear, CoreSpending, \
NoncoreSpending, ObligatedSuppliersCustomerBase, CompulsorySupplierFractionOfCoreGroup fields.
            revenue: float, a total revenue amount (£) for the levy.
            customers_gas: int [0, inf) annual gas customers (customer or meter count).
            customers_elec: int [0, inf) annual electricity customers (customer or meter count).
            price_cap: str, price cap period to use; default: LATEST.
        """
        # get latest whd values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["TargetSpendingForSchemeYear"].notna().to_numpy().nonzero()[0].max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        whd_levy = cls.calculate_whd_rate(
            df.TargetSpendingForSchemeYear,
            df.CoreSpending,
            df.NoncoreSpending,
            df.ObligatedSuppliersCustomerBase,
            df.CompulsorySupplierFractionOfCoreGroup,
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = df.TargetSpendingForSchemeYear

        if customers_gas and customers_elec:
            gas_weight = customers_gas / (customers_gas + customers_elec)
            elec_weight = 1 - gas_weight
        else:
            gas_weight = np.nan
            elec_weight = np.nan

        return cls(
            name="Warm Homes Discount",
            short_name="whd",
            electricity_weight=elec_weight,
            gas_weight=gas_weight,
            tax_weight=0,
            electricity_variable_weight=0,
            electricity_fixed_weight=1,
            gas_variable_weight=0,
            gas_fixed_weight=1,
            electricity_variable_rate=0,
            electricity_fixed_rate=whd_levy,
            gas_variable_rate=0,
            gas_fixed_rate=whd_levy,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            TargetSpendingForSchemeYear=df.TargetSpendingForSchemeYear,
            CoreSpending=df.CoreSpending,
            NoncoreSpending=df.NoncoreSpending,
            ObligatedSuppliersCustomerBase=df.ObligatedSuppliersCustomerBase,
            CompulsorySupplierFractionOfCoreGroup=df.CompulsorySupplierFractionOfCoreGroup,
        )

    @staticmethod
    def calculate_whd_rate(
        TargetSpendingForSchemeYear: float,
        CoreSpending: float,
        NoncoreSpending: float,
        ObligatedSuppliersCustomerBase: int,
        CompulsorySupplierFractionOfCoreGroup: float,
    ) -> "WHD":
        """Calculate warm homes discount rate for given values."""
        return (
            (TargetSpendingForSchemeYear / ObligatedSuppliersCustomerBase)
            if np.isnan(CoreSpending)
            else (
                (
                    (CoreSpending * CompulsorySupplierFractionOfCoreGroup)
                    + NoncoreSpending
                )
                / ObligatedSuppliersCustomerBase
            )
        )


class ECO(Levy):
    """Energy Company Obligation Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        AnnualisedCostECO4Gas: float, annualised costs for scheme year attributed to gas - ECO4 (£).
        AnnualisedCostECO4Electricity: float, annualised costs for scheme year attributed to electricity - ECO4 (£).
        AnnualisedCostGBISGas: float, annualised costs for scheme year attributed to gas - Great British Insulation Scheme (GBIS) - formally ECO+ (£).
        AnnualisedCostGBISElectricity: float, annualised costs for scheme year attributed to electricity - Great British Insulation Scheme (GBIS) - formally ECO+ (£).
        GDPDeflatorToCurrentPricesECO4: float, inflate annualised costs to current year prices (ECO4 costs are in 2021 prices, %).
        GDPDeflatorToCurrentPricesGBIS: float, inflate annualised costs to current year prices (ECO+/GBIS costs are in 2022 prices, %).
        FullyObligatedShareOfObligatedSupplierSupplyGas: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - gas (%).
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - electricity (%).
        ObligatedSupplierVolumeGas: float, supply volumes of obligated suppliers - gas (MWh).
        ObligatedSupplierVolumeElectricity: float, supply volumes of obligated suppliers - electricity (MWh).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            AnnualisedCostECO4Gas: annualised ECO4 costs for scheme year, gas.",
            "            AnnualisedCostECO4Electricity: annualised ECO4 costs for scheme year, electricity.",
            "            AnnualisedCostGBISGas: annualised ECO+/GBIS costs for scheme year, gas.",
            "            AnnualisedCostGBISElectricity: annualised ECO+/GBIS costs for scheme year, electricity.",
            "            GDPDeflatorToCurrentPricesECO4: inflate ECO4 annualised costs (2021 prices) to current year prices.",
            "            GDPDeflatorToCurrentPricesGBIS: inflate ECO+/GBIS annualised costs (2022 prices) to current year prices.",
            "            FullyObligatedShareOfObligatedSupplierSupplyGas: 'fully' obligated suppliers as a share of all obligated suppliers, gas.",
            "            FullyObligatedShareOfObligatedSupplierSupplyElectricity: 'fully' obligated suppliers as a share of all obligated suppliers, electricity.",
            "            ObligatedSupplierVolumeGas: supply volumes of obligated suppliers, gas.",
            "            ObligatedSupplierVolumeElectricity: supply volumes of obligated suppliers, electricity.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        AnnualisedCostECO4Gas: float,
        AnnualisedCostECO4Electricity: float,
        AnnualisedCostGBISGas: float,
        AnnualisedCostGBISElectricity: float,
        GDPDeflatorToCurrentPricesECO4: float,
        GDPDeflatorToCurrentPricesGBIS: float,
        FullyObligatedShareOfObligatedSupplierSupplyGas: float,
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float,
        ObligatedSupplierVolumeGas: float,
        ObligatedSupplierVolumeElectricity: float,
    ) -> None:
        super(ECO, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.AnnualisedCostECO4Gas = AnnualisedCostECO4Gas
        self.AnnualisedCostECO4Electricity = AnnualisedCostECO4Electricity
        self.AnnualisedCostGBISGas = AnnualisedCostGBISGas
        self.AnnualisedCostGBISElectricity = AnnualisedCostGBISElectricity
        self.GDPDeflatorToCurrentPricesECO4 = GDPDeflatorToCurrentPricesECO4
        self.GDPDeflatorToCurrentPricesGBIS = GDPDeflatorToCurrentPricesGBIS
        self.FullyObligatedShareOfObligatedSupplierSupplyGas = (
            FullyObligatedShareOfObligatedSupplierSupplyGas
        )
        self.FullyObligatedShareOfObligatedSupplierSupplyElectricity = (
            FullyObligatedShareOfObligatedSupplierSupplyElectricity
        )
        self.ObligatedSupplierVolumeGas = ObligatedSupplierVolumeGas
        self.ObligatedSupplierVolumeElectricity = ObligatedSupplierVolumeElectricity

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, price_cap: str = "LATEST"
    ) -> "ECO":
        """Create ECO levy instance from dataframe input.

        Uses the `process_data_ECO()` output from `asf_levies_model.getters.load_data` to \
initialise an ECO levy object at present values.

        As ECO has stated scheme costs, these are used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, AnnualisedCostECO4Gas, \
AnnualisedCostECO4Electricity, AnnualisedCostGBISGas, AnnualisedCostGBISElectricity, \
GDPDeflatorToCurrentPricesECO4, GDPDeflatorToCurrentPricesGBIS, \
FullyObligatedShareOfObligatedSupplierSupplyGas, \
FullyObligatedShareOfObligatedSupplierSupplyElectricity, ObligatedSupplierVolumeGas, \
ObligatedSupplierVolumeElectricity, fields.
            revenue: float, a total revenue amount (£) for the levy.
            price_cap: str, price cap period to use; default: LATEST.
        """
        # get latest eco values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["AnnualisedCostECO4Gas"].notna().to_numpy().nonzero()[0].max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        eco_levy_gas = cls.calculate_eco_rate(
            df.AnnualisedCostECO4Gas,
            df.AnnualisedCostGBISGas,
            df.GDPDeflatorToCurrentPricesECO4,
            df.GDPDeflatorToCurrentPricesGBIS,
            df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            df.ObligatedSupplierVolumeGas,
        )

        eco_levy_elec = cls.calculate_eco_rate(
            df.AnnualisedCostECO4Electricity,
            df.AnnualisedCostGBISElectricity,
            df.GDPDeflatorToCurrentPricesECO4,
            df.GDPDeflatorToCurrentPricesGBIS,
            df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            df.ObligatedSupplierVolumeElectricity,
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = (
                (
                    df.AnnualisedCostECO4Gas
                    * (1 + df.GDPDeflatorToCurrentPricesECO4 / 100)
                )
                + (
                    df.AnnualisedCostECO4Electricity
                    * (1 + df.GDPDeflatorToCurrentPricesECO4 / 100)
                )
                + (
                    df.AnnualisedCostGBISGas
                    * (1 + df.GDPDeflatorToCurrentPricesGBIS / 100)
                )
                + (
                    df.AnnualisedCostGBISElectricity
                    * (1 + df.GDPDeflatorToCurrentPricesGBIS / 100)
                )
            )

        return cls(
            name="Energy Company Obligation",
            short_name="eco",
            electricity_weight=0.5,
            gas_weight=0.5,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=1,
            gas_fixed_weight=0,
            electricity_variable_rate=eco_levy_elec,
            electricity_fixed_rate=0,
            gas_variable_rate=eco_levy_gas,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            AnnualisedCostECO4Gas=df.AnnualisedCostECO4Gas,
            AnnualisedCostECO4Electricity=df.AnnualisedCostECO4Electricity,
            AnnualisedCostGBISGas=df.AnnualisedCostGBISGas,
            AnnualisedCostGBISElectricity=df.AnnualisedCostGBISElectricity,
            GDPDeflatorToCurrentPricesECO4=df.GDPDeflatorToCurrentPricesECO4,
            GDPDeflatorToCurrentPricesGBIS=df.GDPDeflatorToCurrentPricesGBIS,
            FullyObligatedShareOfObligatedSupplierSupplyGas=df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            FullyObligatedShareOfObligatedSupplierSupplyElectricity=df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            ObligatedSupplierVolumeGas=df.ObligatedSupplierVolumeGas,
            ObligatedSupplierVolumeElectricity=df.ObligatedSupplierVolumeElectricity,
        )

    @staticmethod
    def calculate_eco_rate(
        AnnualisedCostECO4: float,
        AnnualisedCostGBIS: float,
        GDPDeflatorToCurrentPricesECO4: float,
        GDPDeflatorToCurrentPricesGBIS: float,
        FullyObligatedShareOfObligatedSupplierSupply: float,
        ObligatedSupplierVolume: float,
    ):
        """Calculate ECO levy rate from given values."""
        if (not np.isnan(AnnualisedCostECO4)) & (not np.isnan(AnnualisedCostGBIS)):
            rate = (
                (AnnualisedCostECO4 * (1 + GDPDeflatorToCurrentPricesECO4 / 100))
                + (AnnualisedCostGBIS * (1 + GDPDeflatorToCurrentPricesGBIS / 100))
            ) / ObligatedSupplierVolume
        elif (not np.isnan(AnnualisedCostECO4)) & (
            np.isnan(FullyObligatedShareOfObligatedSupplierSupply)
        ):
            rate = (
                AnnualisedCostECO4 * (1 + GDPDeflatorToCurrentPricesECO4 / 100)
            ) / ObligatedSupplierVolume
        elif (not np.isnan(AnnualisedCostECO4)) & (
            not np.isnan(FullyObligatedShareOfObligatedSupplierSupply)
        ):
            if np.isnan(GDPDeflatorToCurrentPricesECO4):
                GDPDeflatorToCurrentPricesECO4 = 0
            rate = (
                (AnnualisedCostECO4 * FullyObligatedShareOfObligatedSupplierSupply)
                * (1 + GDPDeflatorToCurrentPricesECO4 / 100)
            ) / ObligatedSupplierVolume
        else:
            raise ValueError("Insufficient information to calculate ECO rate.")
        return rate


class FIT(Levy):
    """Feed-In Tariff Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    LookupPeriod: str, year winter/summer lookup.
        InflatedLevelisationFund: float, inflated Levelisation fund (£).
        TotalElectricitySupplied: float, total Electricity supplied (MWh).
        ExemptSupplyOutsideUK: float, exempt supply for renewable electricity from outside the UK (MWh).
        ExemptSupplyEII: float, exempt supply for Energy Intensive Industry (MWh).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    LookupPeriod: year winter/summer lookup.",
            "            InflatedLevelisationFund: inflated Levelisation fund (£).",
            "            TotalElectricitySupplied: total Electricity supplied (MWh).",
            "            ExemptSupplyOutsideUK: exempt supply for renewable electricity from outside the UK (MWh).",
            "            ExemptSupplyEII: exempt supply for Energy Intensive Industry (MWh)",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        LookupPeriod: str,
        InflatedLevelisationFund: float,
        TotalElectricitySupplied: float,
        ExemptSupplyOutsideUK: float,
        ExemptSupplyEII: float,
    ) -> None:
        super(FIT, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.LookupPeriod = LookupPeriod
        self.InflatedLevelisationFund = InflatedLevelisationFund
        self.TotalElectricitySupplied = TotalElectricitySupplied
        self.ExemptSupplyOutsideUK = ExemptSupplyOutsideUK
        self.ExemptSupplyEII = ExemptSupplyEII

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        scaling_factor: float = 1.0,
        price_cap: str = "LATEST",
    ) -> "FIT":
        """Create FIT levy instance from dataframe input.

        Uses the `process_data_FIT()` output from `asf_levies_model.getters.load_data` to \
initialise a FIT levy object at present values.

        As FIT has a stated scheme cost, this is used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with ChargeRestrictionPeriod1, ChargeRestrictionPeriod2, \
LookupPeriod, InflatedLevelisationFund, TotalElectricitySupplied, ExemptSupplyOutsideUK, \
ExemptSupplyEII, ChargeRestrictionPeriod2_start, ChargeRestrictionPeriod2_end fields.
            revenue: float, a total revenue amount (£) for the levy.
            scaling_factor: float, factor to scale total revenue amount (£) to reflect e.g. only domestic share.
            price_cap: str, price cap period to use; default: LATEST.
        """
        # get latest fit values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["TotalElectricitySupplied"].notna().to_numpy().nonzero()[0].max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        fit_levy = cls.calculate_feed_in_tariff_rate(
            df.InflatedLevelisationFund,
            df.TotalElectricitySupplied,
            df.ExemptSupplyOutsideUK,
            df.ExemptSupplyEII,
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = df.InflatedLevelisationFund * scaling_factor
        else:
            revenue *= scaling_factor

        return cls(
            name="Feed in Tariff",
            short_name="fit",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=0,
            electricity_variable_rate=fit_levy,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            LookupPeriod=df.LookupPeriod,
            InflatedLevelisationFund=df.InflatedLevelisationFund,
            TotalElectricitySupplied=df.TotalElectricitySupplied,
            ExemptSupplyOutsideUK=df.ExemptSupplyOutsideUK,
            ExemptSupplyEII=df.ExemptSupplyEII,
        )

    @staticmethod
    def calculate_feed_in_tariff_rate(
        InflatedLevelisationFund: float,
        TotalElectricitySupplied: float,
        ExemptSupplyOutsideUK: float,
        ExemptSupplyEII: float,
    ) -> float:
        """Calculate Feed-in Tariff rate from given values."""
        return InflatedLevelisationFund / (
            TotalElectricitySupplied - ExemptSupplyOutsideUK - ExemptSupplyEII
        )


class ECO4(Levy):
    """Energy Company Obligation ECO4 Levy.\n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        AnnualisedCostECO4Gas: float, annualised costs for scheme year attributed to gas - ECO4 (£).
        AnnualisedCostECO4Electricity: float, annualised costs for scheme year attributed to electricity - ECO4 (£).
        GDPDeflatorToCurrentPricesECO4: float, inflate annualised costs to current year prices (ECO4 costs are in 2021 prices, %).
        FullyObligatedShareOfObligatedSupplierSupplyGas: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - gas (%).
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - electricity (%).
        ObligatedSupplierVolumeGas: float, supply volumes of obligated suppliers - gas (MWh).
        ObligatedSupplierVolumeElectricity: float, supply volumes of obligated suppliers - electricity (MWh).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            AnnualisedCostECO4Gas: annualised ECO4 costs for scheme year, gas.",
            "            AnnualisedCostECO4Electricity: annualised ECO4 costs for scheme year, electricity.",
            "            GDPDeflatorToCurrentPricesECO4: inflate ECO4 annualised costs (2021 prices) to current year prices.",
            "            FullyObligatedShareOfObligatedSupplierSupplyGas: 'fully' obligated suppliers as a share of all obligated suppliers, gas.",
            "            FullyObligatedShareOfObligatedSupplierSupplyElectricity: 'fully' obligated suppliers as a share of all obligated suppliers, electricity.",
            "            ObligatedSupplierVolumeGas: supply volumes of obligated suppliers, gas.",
            "            ObligatedSupplierVolumeElectricity: supply volumes of obligated suppliers, electricity.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        AnnualisedCostECO4Gas: float,
        AnnualisedCostECO4Electricity: float,
        GDPDeflatorToCurrentPricesECO4: float,
        FullyObligatedShareOfObligatedSupplierSupplyGas: float,
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float,
        ObligatedSupplierVolumeGas: float,
        ObligatedSupplierVolumeElectricity: float,
    ) -> None:
        super(ECO4, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.AnnualisedCostECO4Gas = AnnualisedCostECO4Gas
        self.AnnualisedCostECO4Electricity = AnnualisedCostECO4Electricity
        self.GDPDeflatorToCurrentPricesECO4 = GDPDeflatorToCurrentPricesECO4
        self.FullyObligatedShareOfObligatedSupplierSupplyGas = (
            FullyObligatedShareOfObligatedSupplierSupplyGas
        )
        self.FullyObligatedShareOfObligatedSupplierSupplyElectricity = (
            FullyObligatedShareOfObligatedSupplierSupplyElectricity
        )
        self.ObligatedSupplierVolumeGas = ObligatedSupplierVolumeGas
        self.ObligatedSupplierVolumeElectricity = ObligatedSupplierVolumeElectricity

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, price_cap: str = "LATEST"
    ) -> "ECO4":
        """Create ECO4 levy instance from dataframe input.

        Uses the `process_data_ECO()` output from `asf_levies_model.getters.load_data` to \
initialise an ECO4 levy object at present values.

        As ECO4 has stated scheme costs, these are used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, AnnualisedCostECO4Gas, \
AnnualisedCostECO4Electricity, \
GDPDeflatorToCurrentPricesECO4, \
FullyObligatedShareOfObligatedSupplierSupplyGas, \
FullyObligatedShareOfObligatedSupplierSupplyElectricity, ObligatedSupplierVolumeGas, \
ObligatedSupplierVolumeElectricity, fields.
            revenue: float, a total revenue amount (£) for the levy.
            price_cap: str, price cap period to use; default: LATEST.
        """
        # get latest eco values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["AnnualisedCostECO4Gas"].notna().to_numpy().nonzero()[0].max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        eco4_levy_gas = cls.calculate_eco4_rate(
            df.AnnualisedCostECO4Gas,
            df.GDPDeflatorToCurrentPricesECO4,
            df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            df.ObligatedSupplierVolumeGas,
        )

        eco4_levy_elec = cls.calculate_eco4_rate(
            df.AnnualisedCostECO4Electricity,
            df.GDPDeflatorToCurrentPricesECO4,
            df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            df.ObligatedSupplierVolumeElectricity,
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = (
                df.AnnualisedCostECO4Gas * (1 + df.GDPDeflatorToCurrentPricesECO4 / 100)
            ) + (
                df.AnnualisedCostECO4Electricity
                * (1 + df.GDPDeflatorToCurrentPricesECO4 / 100)
            )

        return cls(
            name="Energy Company Obligation, ECO4",
            short_name="eco4",
            electricity_weight=0.5,
            gas_weight=0.5,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=1,
            gas_fixed_weight=0,
            electricity_variable_rate=eco4_levy_elec,
            electricity_fixed_rate=0,
            gas_variable_rate=eco4_levy_gas,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            AnnualisedCostECO4Gas=df.AnnualisedCostECO4Gas,
            AnnualisedCostECO4Electricity=df.AnnualisedCostECO4Electricity,
            GDPDeflatorToCurrentPricesECO4=df.GDPDeflatorToCurrentPricesECO4,
            FullyObligatedShareOfObligatedSupplierSupplyGas=df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            FullyObligatedShareOfObligatedSupplierSupplyElectricity=df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            ObligatedSupplierVolumeGas=df.ObligatedSupplierVolumeGas,
            ObligatedSupplierVolumeElectricity=df.ObligatedSupplierVolumeElectricity,
        )

    @staticmethod
    def calculate_eco4_rate(
        AnnualisedCostECO4: float,
        GDPDeflatorToCurrentPricesECO4: float,
        FullyObligatedShareOfObligatedSupplierSupply: float,
        ObligatedSupplierVolume: float,
    ):
        """Calculate ECO4 levy rate from given values."""
        if (not np.isnan(AnnualisedCostECO4)) & (
            np.isnan(FullyObligatedShareOfObligatedSupplierSupply)
        ):
            rate = (
                AnnualisedCostECO4 * (1 + GDPDeflatorToCurrentPricesECO4 / 100)
            ) / ObligatedSupplierVolume
        elif (not np.isnan(AnnualisedCostECO4)) & (
            not np.isnan(FullyObligatedShareOfObligatedSupplierSupply)
        ):
            if np.isnan(GDPDeflatorToCurrentPricesECO4):
                GDPDeflatorToCurrentPricesECO4 = 0
            rate = (
                (AnnualisedCostECO4 * FullyObligatedShareOfObligatedSupplierSupply)
                * (1 + GDPDeflatorToCurrentPricesECO4 / 100)
            ) / ObligatedSupplierVolume
        else:
            raise ValueError("Insufficient information to calculate ECO rate.")
        return rate


class GBIS(Levy):
    """Energy Company Obligation Levy, GBIS. \n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        AnnualisedCostGBISGas: float, annualised costs for scheme year attributed to gas - Great British Insulation Scheme (GBIS) - formally ECO+ (£).
        AnnualisedCostGBISElectricity: float, annualised costs for scheme year attributed to electricity - Great British Insulation Scheme (GBIS) - formally ECO+ (£).
        GDPDeflatorToCurrentPricesGBIS: float, inflate annualised costs to current year prices (ECO+/GBIS costs are in 2022 prices, %).
        FullyObligatedShareOfObligatedSupplierSupplyGas: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - gas (%).
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float, share of supply volumes of all obligated suppliers accounted for by 'fully' obligated suppliers - electricity (%).
        ObligatedSupplierVolumeGas: float, supply volumes of obligated suppliers - gas (MWh).
        ObligatedSupplierVolumeElectricity: float, supply volumes of obligated suppliers - electricity (MWh).
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            AnnualisedCostGBISGas: annualised ECO+/GBIS costs for scheme year, gas.",
            "            AnnualisedCostGBISElectricity: annualised ECO+/GBIS costs for scheme year, electricity.",
            "            GDPDeflatorToCurrentPricesGBIS: inflate ECO+/GBIS annualised costs (2022 prices) to current year prices.",
            "            FullyObligatedShareOfObligatedSupplierSupplyGas: 'fully' obligated suppliers as a share of all obligated suppliers, gas.",
            "            FullyObligatedShareOfObligatedSupplierSupplyElectricity: 'fully' obligated suppliers as a share of all obligated suppliers, electricity.",
            "            ObligatedSupplierVolumeGas: supply volumes of obligated suppliers, gas.",
            "            ObligatedSupplierVolumeElectricity: supply volumes of obligated suppliers, electricity.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        AnnualisedCostGBISGas: float,
        AnnualisedCostGBISElectricity: float,
        GDPDeflatorToCurrentPricesGBIS: float,
        FullyObligatedShareOfObligatedSupplierSupplyGas: float,
        FullyObligatedShareOfObligatedSupplierSupplyElectricity: float,
        ObligatedSupplierVolumeGas: float,
        ObligatedSupplierVolumeElectricity: float,
    ) -> None:
        super(GBIS, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.AnnualisedCostGBISGas = AnnualisedCostGBISGas
        self.AnnualisedCostGBISElectricity = AnnualisedCostGBISElectricity
        self.GDPDeflatorToCurrentPricesGBIS = GDPDeflatorToCurrentPricesGBIS
        self.FullyObligatedShareOfObligatedSupplierSupplyGas = (
            FullyObligatedShareOfObligatedSupplierSupplyGas
        )
        self.FullyObligatedShareOfObligatedSupplierSupplyElectricity = (
            FullyObligatedShareOfObligatedSupplierSupplyElectricity
        )
        self.ObligatedSupplierVolumeGas = ObligatedSupplierVolumeGas
        self.ObligatedSupplierVolumeElectricity = ObligatedSupplierVolumeElectricity

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, price_cap: str = "LATEST"
    ) -> "GBIS":
        """Create GBIS levy instance from dataframe input.

        Uses the `process_data_ECO()` output from `asf_levies_model.getters.load_data` to \
initialise an GBIS levy object at present values.

        As GBIS has stated scheme costs, these are used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, \
AnnualisedCostGBISGas, AnnualisedCostGBISElectricity, \
GDPDeflatorToCurrentPricesGBIS, \
FullyObligatedShareOfObligatedSupplierSupplyGas, \
FullyObligatedShareOfObligatedSupplierSupplyElectricity, ObligatedSupplierVolumeGas, \
ObligatedSupplierVolumeElectricity, fields.
            revenue: float, a total revenue amount (£) for the levy.
            price_cap: str, price cap period to use; default: LATEST.
        """
        # get latest eco values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["AnnualisedCostGBISGas"].notna().to_numpy().nonzero()[0].max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        gbis_levy_gas = cls.calculate_gbis_rate(
            df.AnnualisedCostGBISGas,
            df.GDPDeflatorToCurrentPricesGBIS,
            df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            df.ObligatedSupplierVolumeGas,
        )

        gbis_levy_elec = cls.calculate_gbis_rate(
            df.AnnualisedCostGBISElectricity,
            df.GDPDeflatorToCurrentPricesGBIS,
            df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            df.ObligatedSupplierVolumeElectricity,
        )

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        if not revenue:
            revenue = (
                df.AnnualisedCostGBISGas * (1 + df.GDPDeflatorToCurrentPricesGBIS / 100)
            ) + (
                df.AnnualisedCostGBISElectricity
                * (1 + df.GDPDeflatorToCurrentPricesGBIS / 100)
            )

        return cls(
            name="Energy Company Obligation, GBIS.",
            short_name="gbis",
            electricity_weight=0.5,
            gas_weight=0.5,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=1,
            gas_fixed_weight=0,
            electricity_variable_rate=gbis_levy_elec,
            electricity_fixed_rate=0,
            gas_variable_rate=gbis_levy_gas,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            AnnualisedCostGBISGas=df.AnnualisedCostGBISGas,
            AnnualisedCostGBISElectricity=df.AnnualisedCostGBISElectricity,
            GDPDeflatorToCurrentPricesGBIS=df.GDPDeflatorToCurrentPricesGBIS,
            FullyObligatedShareOfObligatedSupplierSupplyGas=df.FullyObligatedShareOfObligatedSupplierSupplyGas,
            FullyObligatedShareOfObligatedSupplierSupplyElectricity=df.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            ObligatedSupplierVolumeGas=df.ObligatedSupplierVolumeGas,
            ObligatedSupplierVolumeElectricity=df.ObligatedSupplierVolumeElectricity,
        )

    @staticmethod
    def calculate_gbis_rate(
        AnnualisedCostGBIS: float,
        GDPDeflatorToCurrentPricesGBIS: float,
        FullyObligatedShareOfObligatedSupplierSupply: float,
        ObligatedSupplierVolume: float,
    ):
        """Calculate GBIS levy rate from given values."""
        if not np.isnan(AnnualisedCostGBIS):
            rate = (
                (AnnualisedCostGBIS * (1 + GDPDeflatorToCurrentPricesGBIS / 100))
            ) / ObligatedSupplierVolume
        else:
            raise ValueError("Insufficient information to calculate GBIS rate.")
        return rate


class NRAB(Levy):
    """Nuclear Regulated Asset Base Levy, nRAB. \n"""

    __doc__ += (
        Levy.__doc__.split("\n", maxsplit=4)[4]
        + """\
    UpdateDate: datetime, month and year ofgem data was updated.
        SchemeYear: str, year of interest.
        OperationalCostsLevy: float, operational Costs Levy rate for charging year.
        InterimLevyRate_AprJun: float, interim Levy rate, dates are for financial years.
        InterimLevyRate_JulSep: float, interim Levy rate, dates are for financial years.
        InterimLevyRate_OctDec: float, interim Levy rate, dates are for financial years.
        InterimLevyRate_JanMar: float, interim Levy rate, dates are for financial years.
        DemandWeight1_AprJun: float, demand weight for profile class 1.
        DemandWeight1_JulSep: float, demand weight for profile class 1.
        DemandWeight1_OctDec: float, demand weight for profile class 1.
        DemandWeight1_JanMar: float, demand weight for profile class 1.
        DemandWeight2_AprJun: float, demand weight for profile class 2.
        DemandWeight2_JulSep: float, demand weight for profile class 2.
        DemandWeight2_OctDec: float, demand weight for profile class 2.
        DemandWeight2_JanMar: float, demand weight for profile class 2.
        ExpectedPayment_Dec25: float, for costs incurred in December 2025, costs added separately to ensure full cost recovery.
        ForecastDemand_Dec25: float, to allow recovery of December 2025 operational costs.
        ForecastDemand_JanMar26: float, to spread the recovery of costs already incurred over 3 months,costs incurred divided over Q1 2026 demand.
"""
    )

    @_generate_docstring(
        Levy.__init__.__doc__,
        [
            "    UpdateDate: month and year of ofgem update.",
            "            SchemeYear: year of interest.",
            "            OperationalCostsLevy: Operational Costs Levy rate for charging year.",
            "            InterimLevyRate_AprJun: Interim Levy rate, dates are for financial years.",
            "            InterimLevyRate_JulSep: Interim Levy rate, dates are for financial years.",
            "            InterimLevyRate_OctDec: Interim Levy rate, dates are for financial years.",
            "            InterimLevyRate_JanMar: Interim Levy rate, dates are for financial years.",
            "            DemandWeight1_AprJun: Demand weight for profile class 1.",
            "            DemandWeight1_JulSep: Demand weight for profile class 1.",
            "            DemandWeight1_OctDec: Demand weight for profile class 1.",
            "            DemandWeight1_JanMar: Demand weight for profile class 1.",
            "            DemandWeight2_AprJun: Demand weight for profile class 2.",
            "            DemandWeight2_JulSep: Demand weight for profile class 2.",
            "            DemandWeight2_OctDec: Demand weight for profile class 2.",
            "            DemandWeight2_JanMar: Demand weight for profile class 2.",
            "            ExpectedPayment_Dec25: For costs incurred in December 2025, costs added separately to ensure full cost recovery.",
            "            ForecastDemand_Dec25: To allow recovery of December 2025 operational costs.",
            "            ForecastDemand_JanMar26: To spread the recovery of costs already incurred over 3 months,costs incurred divided over Q1 2026 demand.",
        ],
    )
    def __init__(
        self,
        name: str,
        short_name: str,
        electricity_weight: float,
        gas_weight: float,
        tax_weight: float,
        electricity_variable_weight: float,
        electricity_fixed_weight: float,
        gas_variable_weight: float,
        gas_fixed_weight: float,
        electricity_variable_rate: float,
        electricity_fixed_rate: float,
        gas_variable_rate: float,
        gas_fixed_rate: float,
        general_taxation: float,
        revenue: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
        UpdateDate: datetime,
        SchemeYear: str,
        OperationalCostsLevy: float,
        InterimLevyRate_AprJun: float,
        InterimLevyRate_JulSep: float,
        InterimLevyRate_OctDec: float,
        InterimLevyRate_JanMar: float,
        DemandWeight1_AprJun: float,
        DemandWeight1_JulSep: float,
        DemandWeight1_OctDec: float,
        DemandWeight1_JanMar: float,
        DemandWeight2_AprJun: float,
        DemandWeight2_JulSep: float,
        DemandWeight2_OctDec: float,
        DemandWeight2_JanMar: float,
        ExpectedPayment_Dec25: float,
        ForecastDemand_Dec25: float,
        ForecastDemand_JanMar26: float,
    ) -> None:
        super(NRAB, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            electricity_variable_weight,
            electricity_fixed_weight,
            gas_variable_weight,
            gas_fixed_weight,
            electricity_variable_rate,
            electricity_fixed_rate,
            gas_variable_rate,
            gas_fixed_rate,
            general_taxation,
            revenue,
            price_cap_period,
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.OperationalCostsLevy = (OperationalCostsLevy,)
        self.InterimLevyRate_AprJun = (InterimLevyRate_AprJun,)
        self.InterimLevyRate_JulSep = (InterimLevyRate_JulSep,)
        self.InterimLevyRate_OctDec = (InterimLevyRate_OctDec,)
        self.InterimLevyRate_JanMar = (InterimLevyRate_JanMar,)
        self.DemandWeight1_AprJun = (DemandWeight1_AprJun,)
        self.DemandWeight1_JulSep = (DemandWeight1_JulSep,)
        self.DemandWeight1_OctDec = (DemandWeight1_OctDec,)
        self.DemandWeight1_JanMar = (DemandWeight1_JanMar,)
        self.DemandWeight2_AprJun = (DemandWeight2_AprJun,)
        self.DemandWeight2_JulSep = (DemandWeight2_JulSep,)
        self.DemandWeight2_OctDec = (DemandWeight2_OctDec,)
        self.DemandWeight2_JanMar = (DemandWeight2_JanMar,)
        self.ExpectedPayment_Dec25 = (ExpectedPayment_Dec25,)
        self.ForecastDemand_Dec25 = (ForecastDemand_Dec25,)
        self.ForecastDemand_JanMar26 = ForecastDemand_JanMar26

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        revenue: float = None,
        denominator: float = None,
        metering_arrangement=None,
        price_cap: str = "LATEST",
    ) -> "GBIS":
        """Create nRAB levy instance from dataframe input.

        Uses the `process_data_NRAB()` output from `asf_levies_model.getters.load_data` to \
initialise an NRAB levy object at present values.

        As NRAB doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator in MWh given to calculate it from the levy value.

        NRAB has a different levy rate according to 'single rate' or 'multi-register' metering. \
As such, the metering arrangement must be selected.

        Owing to delays in commencing the levy, the first levy rate (Jan-Mar 2026) is calculated \
differently from subsequent levies so that costs from the scheme commencement (Dec 2025) can be \
recovered.

        price_cap can be specified to use values for a specific price cap. The default is latest. \
To specify a specific price cap period supply a date in the form `YYYY-MM-DD` that falls within the \
price cap period of interest.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, \
OperationalCostsLevy, InterimLevyRate_AprJun, \
InterimLevyRate_JulSep, InterimLevyRate_OctDec, InterimLevyRate_JanMar, \
DemandWeight1_AprJun, DemandWeight1_JulSep, DemandWeight1_OctDec, \
DemandWeight1_JanMar, DemandWeight2_AprJun, DemandWeight2_JulSep, \
DemandWeight2_OctDec, DemandWeight2_JanMart, ExpectedPayment_Dec25, \
ForecastDemand_Dec25, ForecastDemand_JanMar26, fields.
            revenue: float, a total revenue amount (£) for the levy.
            metering_arrangement: str, either 'single-rate' or 'multi-register'.
            price_cap: str, price cap period to use; default: LATEST.
        """
        if not metering_arrangement:
            raise ValueError(
                "Metering arrangement must be given as either 'single-rate' or 'multi-register'."
            )
        if metering_arrangement not in ["single-rate" or "multi-register"]:
            raise ValueError(
                "Metering arrangement must be given as either 'single-rate' or 'multi-register'."
            )

        # get latest NRAB values from df
        if price_cap == "LATEST":
            # Get first index where data is not captured
            latest_index = (
                df["Operational Costs Levy rate for charging year"]
                .notna()
                .to_numpy()
                .nonzero()[0]
                .max()
            )

            df = df.iloc[latest_index]
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            mask = df.index.map(
                lambda row: True if price_cap_date in row[1] else False
            ).to_numpy()
            if mask.sum() == 0:
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            elif mask.sum() > 1:
                # Use most recent matching period
                df = df.loc[mask].iloc[-1]
                warnings.warn(
                    f"Multiple price cap periods returned, using price cap period {df.name[1].left.strftime('%Y-%m-%d')} to {df.name[1].right.strftime('%Y-%m-%d')}"
                )
            else:
                df = df.loc[mask].iloc[0]

        price_cap_period = PriceCapPeriod(
            left=df.name[1].left, right=df.name[1].right, closed="both"
        )

        # First price cap period uses a different calculation.
        if price_cap_period == PriceCapPeriod(
            pd.to_datetime("2026-01-01 00:00:00"),
            pd.to_datetime("2026-03-31 23:59:59"),
            "both",
        ):
            nrab_levy = df["Interim Levy Rate: Jan to Mar of financial year"] + (
                df["Expected payment (December 2025)"]
                / df["Forecast demand for January 2026 to March 2026"]
            )
            # operational levy adjustment
            operational_levy = df["Operational Costs Levy rate for charging year"] + (
                (
                    df["Operational Costs Levy rate for charging year"]
                    * df["Forecast demand for December 2025"]
                )
                / df["Forecast demand for January 2026 to March 2026"]
            )
            # Combine levy rate and operational costs
            nrab_levy = nrab_levy + operational_levy
        else:
            nrab_levy = (
                cls.calculate_nrab_levy(
                    df["Interim Levy Rate: Apr to Jun of financial year"],
                    df["Interim Levy Rate: Jul to Sep of financial year"],
                    df["Interim Levy Rate: Oct to Dec of financial year"],
                    df["Interim Levy Rate: Jan to Mar of financial year"],
                    df["Demand weight, profile class 1: Apr to Jun"],
                    df["Demand weight, profile class 1: Jul to Sep"],
                    df["Demand weight, profile class 1: Oct to Dec"],
                    df["Demand weight, profile class 1: Jan to Mar"],
                    df["Demand weight, profile class 2: Apr to Jun"],
                    df["Demand weight, profile class 2: Jul to Sep"],
                    df["Demand weight, profile class 2: Oct to Dec"],
                    df["Demand weight, profile class 2: Jan to Mar"],
                    metering_arrangement,
                )
                + df["Operational Costs Levy rate for charging year"]
            )

        # TODO: Add losses adjustment here.

        if not revenue:
            revenue = nrab_levy * denominator

        return cls(
            name=f"Nuclear Regulated Asset Base (nRAB), {metering_arrangement} metering",
            short_name="nrab",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            electricity_variable_weight=1,
            electricity_fixed_weight=0,
            gas_variable_weight=0,
            gas_fixed_weight=0,
            electricity_variable_rate=nrab_levy,
            electricity_fixed_rate=0,
            gas_variable_rate=0,
            gas_fixed_rate=0,
            general_taxation=0,
            revenue=revenue,
            price_cap_period=price_cap_period,
            UpdateDate=df.UpdateDate,
            SchemeYear=df.SchemeYear,
            OperationalCostsLevy=df["Operational Costs Levy rate for charging year"],
            InterimLevyRate_AprJun=df[
                "Interim Levy Rate: Apr to Jun of financial year"
            ],
            InterimLevyRate_JulSep=df[
                "Interim Levy Rate: Jul to Sep of financial year"
            ],
            InterimLevyRate_OctDec=df[
                "Interim Levy Rate: Oct to Dec of financial year"
            ],
            InterimLevyRate_JanMar=df[
                "Interim Levy Rate: Jan to Mar of financial year"
            ],
            DemandWeight1_AprJun=df["Demand weight, profile class 1: Apr to Jun"],
            DemandWeight1_JulSep=df["Demand weight, profile class 1: Jul to Sep"],
            DemandWeight1_OctDec=df["Demand weight, profile class 1: Oct to Dec"],
            DemandWeight1_JanMar=df["Demand weight, profile class 1: Jan to Mar"],
            DemandWeight2_AprJun=df["Demand weight, profile class 2: Apr to Jun"],
            DemandWeight2_JulSep=df["Demand weight, profile class 2: Jul to Sep"],
            DemandWeight2_OctDec=df["Demand weight, profile class 2: Oct to Dec"],
            DemandWeight2_JanMar=df["Demand weight, profile class 2: Jan to Mar"],
            ExpectedPayment_Dec25=df["Expected payment (December 2025)"],
            ForecastDemand_Dec25=df["Forecast demand for December 2025"],
            ForecastDemand_JanMar26=df[
                "Forecast demand for January 2026 to March 2026"
            ],
        )

    @staticmethod
    def calculate_nrab_levy(
        InterimLevyRate_AprJun: float,
        InterimLevyRate_JulSep: float,
        InterimLevyRate_OctDec: float,
        InterimLevyRate_JanMar: float,
        DemandWeight1_AprJun: float,
        DemandWeight1_JulSep: float,
        DemandWeight1_OctDec: float,
        DemandWeight1_JanMar: float,
        DemandWeight2_AprJun: float,
        DemandWeight2_JulSep: float,
        DemandWeight2_OctDec: float,
        DemandWeight2_JanMar: float,
        metering_arrangement: str,
    ):
        """Calculate nRAB levy rate from given values."""
        if metering_arrangement == "single-rate":
            rate = (
                (InterimLevyRate_AprJun * DemandWeight1_AprJun)
                + (InterimLevyRate_JulSep * DemandWeight1_JulSep)
                + (InterimLevyRate_OctDec * DemandWeight1_OctDec)
                + (InterimLevyRate_JanMar * DemandWeight1_JanMar)
            )
        elif metering_arrangement == "multi-register":
            rate = (
                (InterimLevyRate_AprJun * DemandWeight2_AprJun)
                + (InterimLevyRate_JulSep * DemandWeight2_JulSep)
                + (InterimLevyRate_OctDec * DemandWeight2_OctDec)
                + (InterimLevyRate_JanMar * DemandWeight2_JanMar)
            )
        else:
            raise ValueError("Insufficient information to calculate nRAB rate.")
        return rate


class LevyCollection:
    """A container for Levy objects.

    Convenient abstraction for working with multiple levies.
    """

    def __init__(
        self,
        name: str,
        short_name: str,
        levies: list,
        denominators: Union[Dict[str, int], Dict[str, Dict[str, int]]],
    ) -> None:
        """Initializes the Levy collection instance based on list of provided levies.

        Args:
            name: Name for LevyCollection instance.
            short_name: Abbreviation for LevyCollection instance.
            levies: List of Levy objects.
            denominators: A single set of denominators to apply to all levies, or a dictionary of levy specific denominators.
        """
        # Ensure all levies have the same price cap period
        if not all(
            levy.price_cap_period == levies[0].price_cap_period for levy in levies
        ):
            raise ValueError("All levies must have the same price_cap_period")

        self.name = name
        self.short_name = short_name
        self.levies = levies
        self.denominators = denominators

    @property
    def price_cap_period(self) -> PriceCapPeriod:
        return self.levies[0].price_cap_period

    @property
    def levy_short_names(self) -> List[str]:
        return [levy.short_name for levy in self.levies]

    @property
    def denominators(self):
        return self._denominators

    @denominators.setter
    def denominators(self, denominator_values):
        # If denominators dictonary has 1 level, assume it applies to all levies
        if not any(isinstance(i, dict) for i in denominator_values.values()):
            self._denominators = {
                key: denominator_values for key in self.levy_short_names
            }
        # check all keys relate to levies in the collection.
        elif self._check_levies_in_short_names(denominator_values.keys()):
            self._denominators = denominator_values
        else:
            missing_keys = [
                short_name
                for short_name in self.levy_short_names
                if short_name not in denominator_values.keys()
            ]
            raise ValueError(f"{missing_keys} keys missing from denominators.")

    def rebalance_to_denominators(self, inplace=False):
        """Rebalances supplied levies according to supplied denominators.

        Useful for internal consistency if denominators differ from ofgem denominators.

        Args:
            inplace: bool, default is to return a new LevyCollection, but can be modified in place.
        """
        rebalancing_weights = {
            levy.short_name: {
                "new_electricity_weight": levy.electricity_weight,
                "new_gas_weight": levy.gas_weight,
                "new_tax_weight": levy.tax_weight,
                "new_variable_weight_elec": levy.electricity_variable_weight,
                "new_fixed_weight_elec": levy.electricity_fixed_weight,
                "new_variable_weight_gas": levy.gas_variable_weight,
                "new_fixed_weight_gas": levy.gas_fixed_weight,
            }
            for levy in self.levies
        }

        return self.rebalance_levies(
            rebalancing_weights=rebalancing_weights,
            scenario_name=f"{self.name}_rebalanced",
            inplace=inplace,
        )

    def update_revenues(
        self,
        new_revenues: Dict[str, Union[float, int]],
        overwrite: bool = True,
        inplace: bool = False,
    ) -> Optional["LevyCollection"]:
        """Update levy revenues with new values.

        The default (overwrite = True) sets a new_revenue as revenue and updates the levy rate using
        the provided denominators.

                If overwrite is set to False, the revenue is modified by new_revenue, a positive value
        increases revenue (i.e. revenue = revenue + new_revenue), while a negative value decreases revenue
        (i.e. revenue = revenue - new_revenue).

        The new_revenues dictionary sets the levy short_name as the key and the new revenue as the value.

        The method uses the LevyCollection denominators to re-estimate the levy rates.

        args:
            new_revenues: dict, levy short name: revenue value pairs to update.
            overwrite: bool (default: True): whether to overwrite existing revenue with new_revenues or modify by new_revenues.
            inplace: bool (default: False): whether to update Levy instance inplace or return new LevyCollection.
        """
        if not self._check_short_names_in_levies(new_revenues.keys()):
            missing = self._get_short_names_not_in_levies(new_revenues.keys())
            raise ValueError(
                f"{', '.join(missing)} not recognised as a levy short name."
            )

        if inplace:
            for key, value in new_revenues.items():
                idx = [levy.short_name == key for levy in self.levies].index(True)
                self.levies[idx].update_revenue(
                    new_revenue=value,
                    **self.denominators[key],
                    overwrite=overwrite,
                    inplace=inplace,
                )
            self.name = self.name + "_revenue_updated"
        else:
            levies = []
            for levy in self.levies:
                for key, value in new_revenues.items():
                    if levy.short_name != key:
                        levies.append(levy)
                    elif levy.short_name == key:
                        levies.append(
                            levy.update_revenue(
                                new_revenue=value,
                                **self.denominators[key],
                                overwrite=overwrite,
                                inplace=inplace,
                            )
                        )
                    else:
                        raise ValueError("Error updating revenues.")
            return LevyCollection(
                name=self.name + "_revenue_updated",
                short_name=self.short_name,
                levies=levies,
                denominators=self.denominators,
            )

    def union_levies(self, by: Optional[List[str]] = None) -> Levy:
        """Collapse levies into single generic levy.

        Args:
            by: List of levy short names to union, defaults None (all levies).
        """
        if by:
            if not self._check_short_names_in_levies(by):
                bad_short_names = self._get_short_names_not_in_levies(by)
                raise ValueError(
                    f"{bad_short_names} passed to `by` not recognised as levy short names."
                )
        if not by:
            by = self.levy_short_names

        # Get revenue
        total_revenue = sum(
            [levy.revenue for levy in self.levies if levy.short_name in by]
        )
        gas_revenue = sum(
            [
                levy.revenue * levy.gas_weight
                for levy in self.levies
                if levy.short_name in by
            ]
        )
        electricity_revenue = sum(
            [
                levy.revenue * levy.electricity_weight
                for levy in self.levies
                if levy.short_name in by
            ]
        )

        # get combined rates
        electricity_variable_rate = sum(
            [
                levy.electricity_variable_rate
                for levy in self.levies
                if levy.short_name in by
            ]
        )
        electricity_fixed_rate = sum(
            [
                levy.electricity_fixed_rate
                for levy in self.levies
                if levy.short_name in by
            ]
        )
        gas_variable_rate = sum(
            [levy.gas_variable_rate for levy in self.levies if levy.short_name in by]
        )
        gas_fixed_rate = sum(
            [levy.gas_fixed_rate for levy in self.levies if levy.short_name in by]
        )

        # get weights
        gas_weight = (
            sum(
                [
                    levy.revenue * levy.gas_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / total_revenue
        )
        electricity_weight = (
            sum(
                [
                    levy.revenue * levy.electricity_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / total_revenue
        )
        tax_weight = (
            sum(
                [
                    levy.revenue * levy.tax_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / total_revenue
        )

        electricity_variable_weight = (
            sum(
                [
                    levy.revenue
                    * levy.electricity_weight
                    * levy.electricity_variable_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / electricity_revenue
        )
        electricity_fixed_weight = (
            sum(
                [
                    levy.revenue
                    * levy.electricity_weight
                    * levy.electricity_fixed_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / electricity_revenue
        )
        gas_variable_weight = (
            sum(
                [
                    levy.revenue * levy.gas_weight * levy.gas_variable_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / gas_revenue
        )
        gas_fixed_weight = (
            sum(
                [
                    levy.revenue * levy.gas_weight * levy.gas_fixed_weight
                    for levy in self.levies
                    if levy.short_name in by
                ]
            )
            / gas_revenue
        )

        return Levy(
            name=f'union_{"_".join(by)}',
            short_name="union",
            electricity_weight=electricity_weight,
            gas_weight=gas_weight,
            tax_weight=tax_weight,
            electricity_variable_weight=electricity_variable_weight,
            electricity_fixed_weight=electricity_fixed_weight,
            gas_variable_weight=gas_variable_weight,
            gas_fixed_weight=gas_fixed_weight,
            electricity_variable_rate=electricity_variable_rate,
            electricity_fixed_rate=electricity_fixed_rate,
            gas_variable_rate=gas_variable_rate,
            gas_fixed_rate=gas_fixed_rate,
            general_taxation=total_revenue * tax_weight,
            revenue=total_revenue,
            price_cap_period=self.price_cap_period,
        )

    def calculate_variable_levies(
        self,
        electricity_consumption: float,
        gas_consumption: float,
        by: Optional[List[str]] = None,
    ) -> float:
        """Calculate variable component of levies for given consumption.

        Args:
            electricity_consumption: float [0, inf), electricity consumption in MWh.
            gas_consumption: float [0, inf), gas consumption in MWh.
            by: List of levy short names to identify levies to use, defaults None (all levies).
        """
        if by:
            if not self._check_short_names_in_levies(by):
                bad_short_names = self._get_short_names_not_in_levies(by)
                raise ValueError(
                    f"{bad_short_names} passed to `by` not recognised as levy short names."
                )
        if not by:
            by = self.levy_short_names

        return sum(
            [
                levy.calculate_variable_levy(electricity_consumption, gas_consumption)
                for levy in self.levies
                if levy.short_name in by
            ]
        )

    def calculate_fixed_levies(
        self,
        electricity_customer: bool,
        gas_customer: bool,
        by: Optional[List[str]] = None,
    ) -> float:
        """Calculate fixed component of levy for given customers.

        Args:
            electricity_customer: bool, whether electricity customer.
            gas_customer: bool, whether gas customer.
            by: List of levy short names to identify levies to use, defaults None (all levies).
        """
        if by:
            if not self._check_short_names_in_levies(by):
                bad_short_names = self._get_short_names_not_in_levies(by)
                raise ValueError(
                    f"{bad_short_names} passed to `by` not recognised as levy short names."
                )
        if not by:
            by = self.levy_short_names

        return sum(
            [
                levy.calculate_fixed_levy(electricity_customer, gas_customer)
                for levy in self.levies
                if levy.short_name in by
            ]
        )

    def calculate_levies(
        self,
        electricity_consumption: float,
        gas_consumption: float,
        electricity_customer: bool,
        gas_customer: bool,
        by: Optional[List[str]] = None,
    ) -> float:
        """Calculate total levy amount (variable + fixed costs) for given consumer profile.

        Args:
            electricity_consumption: float [0, inf), electricity consumption in MWh.
            gas_consumption: float [0, inf), gas consumption in MWh.
            electricity_customer: bool, whether electricity customer.
            gas_customer: bool, whether gas customer.
            by: List of levy short names to identify levies to use, defaults None (all levies).
        """
        return self.calculate_variable_levies(
            electricity_consumption, gas_consumption, by
        ) + self.calculate_fixed_levies(electricity_customer, gas_customer, by)

    def rebalance_levies(
        self,
        rebalancing_weights: Union[
            Dict[str, Dict[str, float]], Dict[str, Dict[str, Dict[str, float]]]
        ],
        scenario_name: Optional[str] = None,
        inplace: bool = False,
    ) -> Optional["LevyCollection"]:
        """Rebalance levies according to a set of rebalancing weights. Uses denominators held by LevyCollection.

        Args:
            rebalancing_weights: dict: weights to rebalance each levy, optionally indexed by scenario_name.
            scenario_name: Optional[str]: scenario name, set as LevyCollection name.
            inplace: bool: Default is to return a new LevyCollection, but can be modified in place.
        """
        # If rebalancing weights are not indexed by scenario, add a scenario level to dictionary.
        if (
            _dictionary_depth(rebalancing_weights) == 2
        ) & self._check_levies_in_short_names(rebalancing_weights.keys()):
            if scenario_name:
                rebalancing_weights = {scenario_name: rebalancing_weights}
            else:
                scenario_name = "rebalancing_scenario"
                rebalancing_weights = {scenario_name: rebalancing_weights}
        # Otherwise check rebalancing weights exist for scenario.
        elif (_dictionary_depth(rebalancing_weights) == 3) & (
            scenario_name in rebalancing_weights.keys()
        ):
            if not self._check_levies_in_short_names(
                rebalancing_weights.get(scenario_name).keys()
            ):
                raise ValueError(
                    "Rebalancing weights need to cover all levies in the levy collection."
                )
        # Otherwise provide useful error handling.
        else:
            if (_dictionary_depth(rebalancing_weights) == 3) & (
                scenario_name not in rebalancing_weights.keys()
            ):
                raise ValueError(
                    "Rebalancing weights not available for given scenario name, or scenario name not provided."
                )
            elif (_dictionary_depth(rebalancing_weights) == 2) & (
                not self._check_levies_in_short_names(rebalancing_weights.keys())
            ):
                raise ValueError(
                    "Rebalancing weights need to cover all levies in the elvy collection."
                )
            else:
                raise ValueError("Error with rebalancign weights. Please check form.")

        # Rebalance levies
        rebalanced_levies = [
            levy.rebalance_levy(
                **rebalancing_weights.get(scenario_name).get(levy.short_name),
                **self.denominators.get(levy.short_name),
            )
            for levy in self.levies
        ]

        if inplace:
            # update levies with rebalanced levies
            self.levies = rebalanced_levies
            self.name = scenario_name
            return None
        else:
            return LevyCollection(
                name=scenario_name,
                short_name=self.short_name,
                levies=rebalanced_levies,
                denominators=self.denominators,
            )

    def summarise_levies(self, include_weights: bool = False) -> pd.DataFrame:
        """Output a summary of key levy statistics to a DataFrame.

        Args:
            include_weights: choose to include levy weights, defaults to False
        """
        desc_attrs = ["name", "short_name", "price_cap_period", "revenue"]
        weight_attrs = [
            "electricity_weight",
            "gas_weight",
            "tax_weight",
            "electricity_variable_weight",
            "electricity_fixed_weight",
            "gas_variable_weight",
            "gas_fixed_weight",
        ]
        rate_attrs = [
            "electricity_variable_rate",
            "electricity_fixed_rate",
            "gas_variable_rate",
            "gas_fixed_rate",
            "general_taxation",
        ]
        if include_weights:
            attrs = desc_attrs + weight_attrs + rate_attrs
        else:
            attrs = desc_attrs + rate_attrs

        data = {
            short_name: {attr: getattr(self[short_name], attr) for attr in attrs}
            for short_name in self.levy_short_names
        }

        return (
            pd.DataFrame(data)
            .T.reset_index(drop=True)
            .assign(price_cap_period=lambda df: df["price_cap_period"].map(repr))
        )

    def _check_short_names_in_levies(self, short_names: List[str]) -> bool:
        """Check if a list of short names all appear in the LevyCollection."""
        return all([short_name in self.levy_short_names for short_name in short_names])

    def _check_levies_in_short_names(self, short_names: List[str]) -> bool:
        """Check if all LevyCollection levies appear in a list of short names."""
        return all([short_name in short_names for short_name in self.levy_short_names])

    def _get_short_names_not_in_levies(self, short_names: List[str]) -> bool:
        """Return list of short names not in LevyCollection."""
        return [
            short_name
            for short_name in short_names
            if short_name not in self.levy_short_names
        ]

    def copy(self, deep: bool = True):
        """Return a copy of the LevyCollection."""
        if deep:
            return copy.deepcopy(self)
        else:
            return copy.copy(self)

    def __getitem__(self, key: Union[str, List[str], Tuple[str]]):
        """Index LevyCollection based on Levy short names."""
        if isinstance(key, str):
            if key in self.levy_short_names:
                return [levy for levy in self.levies if levy.short_name == key][0]
            else:
                raise IndexError(f"{key} not found in levy short names.")
        elif isinstance(key, list) or isinstance(key, tuple):
            if all([k in self.levy_short_names for k in key]):
                return [levy for levy in self.levies if levy.short_name in key]
            else:
                missing = [k for k in key if k not in self.levy_short_names]
                raise IndexError(f"{', '.join(missing)} not found in levy short names.")

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __delitem__(self, key):
        if key in self.levy_short_names:
            self.levies = [levy for levy in self.levies if levy.short_name != key]

    def __iter__(self):
        yield from self.levies

    def __len__(self):
        return len(self.levies)

    def __str__(self):
        return f"LevyCollection containing: {', '.join(self.levy_short_names)} levies."

    def __repr__(self):
        return self.__str__()
