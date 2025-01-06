import copy
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, Union
import warnings

from asf_levies_model.utils.utils import _generate_docstring, PriceCapPeriod


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
                .apply(
                    lambda row: row["TariffCurrentYear"] & row["TariffPreviousYear"],
                    axis=1,
                )
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
