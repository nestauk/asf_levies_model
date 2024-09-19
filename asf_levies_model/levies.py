import copy
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

from asf_levies_model.utils.utils import _generate_docstring


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
        """
        self.name = name
        self.short_name = short_name

        # Mode split
        self.electricity_weight = electricity_weight
        self.gas_weight = gas_weight
        self.tax_weight = tax_weight

        # Levy method
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
            f'Levy(name="{self.name}", short_name="{self.short_name}", {", ".join([f"{attr}={getattr(self, attr)}" for attr in non_zero])})'
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
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.obligation_level = obligation_level
        self.BuyOutPriceSchemeYear = BuyOutPriceSchemeYear
        self.BuyOutPricePreviousYear = BuyOutPricePreviousYear
        self.ForecastAnnualRPIPreviousYear = ForecastAnnualRPIPreviousYear

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, denominator: float = None
    ) -> "RO":
        """Create RO levy instance from dataframe input.

        Uses the `process_data_RO()` output from `asf_levies_model.getters.load_data` to \
initialise a RO levy object at present values.

        As RO doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator in MWh given to calculate it from the levy value (£/MWh).

        Args:
            df: a dataframe with UpdateDate, SchemeYear, obligation_level,\
BuyOutPriceSchemeYear, BuyOutPricePreviousYear, ForecastAnnualRPIPreviousYear fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total supply amount (MWh) to calculate the revenue.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        # get latest ro values from df
        latest = (
            df.loc[lambda df: df["ObligationLevel"].notna()]
            .sort_values("UpdateDate", ascending=False)
            .iloc[0]
        )

        ro_levy = cls.calculate_renewable_obligation_rate(
            latest.ObligationLevel,
            latest.BuyOutPriceSchemeYear,
            latest.BuyOutPricePreviousYear,
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
            UpdateDate=latest.UpdateDate,
            SchemeYear=latest.SchemeYear,
            obligation_level=latest.ObligationLevel,
            BuyOutPriceSchemeYear=latest.BuyOutPriceSchemeYear,
            BuyOutPricePreviousYear=latest.BuyOutPricePreviousYear,
            ForecastAnnualRPIPreviousYear=latest.ForecastAnnualRPIPreviousYear,
        )

    @classmethod
    def calculate_renewable_obligation_rate(
        cls,
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
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.TariffCurrentYear = TariffCurrentYear
        self.TariffPreviousYear = TariffPreviousYear
        self.ForecastAnnualRPIPreviousYear = ForecastAnnualRPIPreviousYear

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, denominator: float = None
    ) -> "AAHEDC":
        """Create AAHEDC levy instance from dataframe input.

        Uses the `process_data_AAHEDC()` output from `asf_levies_model.getters.load_data` to \
initialise an AAHEDC levy object at present values.

        As AAHEDC doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator in MWh given to calculate it from the levy value (£/MWh at GSP).

        Args:
            df: a dataframe with UpdateDate, SchemeYear, TariffCurrentYear,\
TariffPreviousYear, ForecastAnnualRPIPreviousYear fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total supply amount (MWh) to calculate the revenue.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        # get latest aahedc values from df
        latest = (
            df.assign(
                tariff=lambda df: df.apply(
                    lambda x: (
                        x["TariffCurrentYear"]
                        if not np.isnan(x["TariffCurrentYear"])
                        else x["TariffPreviousYear"]
                    ),
                    axis=1,
                )
            )
            .loc[lambda df: df["tariff"].notna()]
            .drop(columns="tariff")
            .sort_values("UpdateDate", ascending=False)
            .iloc[0]
        )

        aahedc_tariff_forecast = cls.calculate_aahedc_tariff_forecast(
            latest.TariffPreviousYear, latest.ForecastAnnualRPIPreviousYear
        )

        aahedc_levy = cls.calculate_aahedc_rate(
            latest.TariffCurrentYear, aahedc_tariff_forecast
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
            UpdateDate=latest.UpdateDate,
            SchemeYear=latest.SchemeYear,
            TariffCurrentYear=latest.TariffCurrentYear,
            TariffPreviousYear=latest.TariffPreviousYear,
            ForecastAnnualRPIPreviousYear=latest.ForecastAnnualRPIPreviousYear,
        )

    @classmethod
    def calculate_aahedc_tariff_forecast(
        cls, TariffPreviousYear: float, ForecastAnnualRPIPreviousYear: float
    ) -> float:
        """Calculate AAHEDC tariff forecast from given values."""
        return TariffPreviousYear * (1 + ForecastAnnualRPIPreviousYear / 100)

    @classmethod
    def calculate_aahedc_rate(
        cls, TariffCurrentYear: float, aahedc_tariff_forecast: float
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
        )
        self.UpdateDate = UpdateDate
        self.SchemeYear = SchemeYear
        self.LevyRate = LevyRate
        self.BackdatedLevyRate = BackdatedLevyRate

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, revenue: float = None, denominator: float = None
    ) -> "GGL":
        """Create GGL levy instance from dataframe input.

        Uses the `process_data_GGL()` output from `asf_levies_model.getters.load_data` to \
initialise a GGL levy object at present values.

        As GGL doesn't have a stated revenue or scheme cost, revenue must either be provided,\
or a denominator (number of meters) given to calculate it from the levy value (£/meter).

        Args:
            df: a dataframe with UpdateDate, SchemeYear, LevyRate, BackdatedLevyRate fields.
            revenue: float, a total revenue amount (£) for the levy.
            denominator: float, a total number of meters (customers) to calculate the revenue.

        Raises:
            ValueError: revenue or denominator must be provided.
        """
        if (revenue is None) & (denominator is None):
            raise ValueError("Please provide either revenue or denominator.")

        # get latest ggl values from df
        latest = (
            df.loc[lambda df: df["LevyRate"].notna()]
            .sort_values("UpdateDate", ascending=False)
            .iloc[0]
        )

        ggl_levy = cls.calculate_ggl_rate(latest.LevyRate, latest.BackdatedLevyRate)

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
            UpdateDate=latest.UpdateDate,
            SchemeYear=latest.SchemeYear,
            LevyRate=latest.LevyRate,
            BackdatedLevyRate=latest.BackdatedLevyRate,
        )

    @classmethod
    def calculate_ggl_rate(cls, LevyRate: float, BackdatedLevyRate: float) -> float:
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
    def from_dataframe(cls, df, revenue=None):
        """Create WHD levy instance from dataframe input.

        Uses the `process_data_WHD()` output from `asf_levies_model.getters.load_data` to \
initialise a WHD levy object at present values.

        As WHD has a stated scheme cost, this is used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, TargetSpendingForSchemeYear, CoreSpending, \
NoncoreSpending, ObligatedSuppliersCustomerBase, CompulsorySupplierFractionOfCoreGroup fields.
            revenue: float, a total revenue amount (£) for the levy.
        """
        # get latest whd values from df
        latest = (
            df.loc[lambda df: df["TargetSpendingForSchemeYear"].notna()]
            .sort_values("UpdateDate", ascending=False)
            .iloc[0]
        )

        whd_levy = cls.calculate_whd_rate(
            latest.TargetSpendingForSchemeYear,
            latest.CoreSpending,
            latest.NoncoreSpending,
            latest.ObligatedSuppliersCustomerBase,
            latest.CompulsorySupplierFractionOfCoreGroup,
        )

        if not revenue:
            revenue = latest.TargetSpendingForSchemeYear

        return cls(
            name="Warm Homes Discount",
            short_name="whd",
            electricity_weight=0.5,
            gas_weight=0.5,
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
            UpdateDate=latest.UpdateDate,
            SchemeYear=latest.SchemeYear,
            TargetSpendingForSchemeYear=latest.TargetSpendingForSchemeYear,
            CoreSpending=latest.CoreSpending,
            NoncoreSpending=latest.NoncoreSpending,
            ObligatedSuppliersCustomerBase=latest.ObligatedSuppliersCustomerBase,
            CompulsorySupplierFractionOfCoreGroup=latest.CompulsorySupplierFractionOfCoreGroup,
        )

    @classmethod
    def calculate_whd_rate(
        cls,
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
    def from_dataframe(cls, df: pd.DataFrame, revenue: float = None) -> "ECO":
        """Create ECO levy instance from dataframe input.

        Uses the `process_data_ECO()` output from `asf_levies_model.getters.load_data` to \
initialise an ECO levy object at present values.

        As ECO has stated scheme costs, these are used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        Args:
            df: a dataframe with UpdateDate, SchemeYear, AnnualisedCostECO4Gas, \
AnnualisedCostECO4Electricity, AnnualisedCostGBISGas, AnnualisedCostGBISElectricity, \
GDPDeflatorToCurrentPricesECO4, GDPDeflatorToCurrentPricesGBIS, \
FullyObligatedShareOfObligatedSupplierSupplyGas, \
FullyObligatedShareOfObligatedSupplierSupplyElectricity, ObligatedSupplierVolumeGas, \
ObligatedSupplierVolumeElectricity, fields.
            revenue: float, a total revenue amount (£) for the levy.
        """
        # get latest eco values from df
        latest = (
            df.loc[lambda df: df["AnnualisedCostECO4Gas"].notna()]
            .sort_values("UpdateDate", ascending=False)
            .iloc[0]
        )

        eco_levy_gas = cls.calculate_eco_rate(
            latest.AnnualisedCostECO4Gas,
            latest.AnnualisedCostGBISGas,
            latest.GDPDeflatorToCurrentPricesECO4,
            latest.GDPDeflatorToCurrentPricesGBIS,
            latest.FullyObligatedShareOfObligatedSupplierSupplyGas,
            latest.ObligatedSupplierVolumeGas,
        )

        eco_levy_elec = cls.calculate_eco_rate(
            latest.AnnualisedCostECO4Electricity,
            latest.AnnualisedCostGBISElectricity,
            latest.GDPDeflatorToCurrentPricesECO4,
            latest.GDPDeflatorToCurrentPricesGBIS,
            latest.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            latest.ObligatedSupplierVolumeElectricity,
        )

        if not revenue:
            revenue = (
                latest.AnnualisedCostECO4Gas
                + latest.AnnualisedCostECO4Electricity
                + latest.AnnualisedCostGBISGas
                + latest.AnnualisedCostGBISElectricity
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
            UpdateDate=latest.UpdateDate,
            SchemeYear=latest.SchemeYear,
            AnnualisedCostECO4Gas=latest.AnnualisedCostECO4Gas,
            AnnualisedCostECO4Electricity=latest.AnnualisedCostECO4Electricity,
            AnnualisedCostGBISGas=latest.AnnualisedCostGBISGas,
            AnnualisedCostGBISElectricity=latest.AnnualisedCostGBISElectricity,
            GDPDeflatorToCurrentPricesECO4=latest.GDPDeflatorToCurrentPricesECO4,
            GDPDeflatorToCurrentPricesGBIS=latest.GDPDeflatorToCurrentPricesGBIS,
            FullyObligatedShareOfObligatedSupplierSupplyGas=latest.FullyObligatedShareOfObligatedSupplierSupplyGas,
            FullyObligatedShareOfObligatedSupplierSupplyElectricity=latest.FullyObligatedShareOfObligatedSupplierSupplyElectricity,
            ObligatedSupplierVolumeGas=latest.ObligatedSupplierVolumeGas,
            ObligatedSupplierVolumeElectricity=latest.ObligatedSupplierVolumeElectricity,
        )

    @classmethod
    def calculate_eco_rate(
        cls,
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
    ChargeRestrictionPeriod1: str, 28AD charge restriction period.
        ChargeRestrictionPeriod2: str, 28AD charge restriction period.
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
            "    ChargeRestrictionPeriod1: 28AD charge restriction period.",
            "            ChargeRestrictionPeriod2: 28AD charge restriction period.",
            "            LookupPeriod: year winter/summer lookup.",
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
        ChargeRestrictionPeriod1: str,
        ChargeRestrictionPeriod2: str,
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
        )
        self.ChargeRestrictionPeriod1 = ChargeRestrictionPeriod1
        self.ChargeRestrictionPeriod2 = ChargeRestrictionPeriod2
        self.LookupPeriod = LookupPeriod
        self.InflatedLevelisationFund = InflatedLevelisationFund
        self.TotalElectricitySupplied = TotalElectricitySupplied
        self.ExemptSupplyOutsideUK = ExemptSupplyOutsideUK
        self.ExemptSupplyEII = ExemptSupplyEII

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, revenue: float = None) -> "FIT":
        """Create FIT levy instance from dataframe input.

        Uses the `process_data_FIT()` output from `asf_levies_model.getters.load_data` to \
initialise a FIT levy object at present values.

        As FIT has a stated scheme cost, this is used by default as the revenue, however a revenue \
value can also be provided if a different value is required.

        Args:
            df: a dataframe with ChargeRestrictionPeriod1, ChargeRestrictionPeriod2, \
LookupPeriod, InflatedLevelisationFund, TotalElectricitySupplied, ExemptSupplyOutsideUK, \
ExemptSupplyEII, ChargeRestrictionPeriod2_start, ChargeRestrictionPeriod2_end fields.
            revenue: float, a total revenue amount (£) for the levy.
        """
        # get latest fit values from df
        latest = (
            df.loc[lambda df: df["TotalElectricitySupplied"].notna()]
            .sort_values("ChargeRestrictionPeriod2_start", ascending=False)
            .iloc[0]
        )

        fit_levy = cls.calculate_feed_in_tariff_rate(
            latest.InflatedLevelisationFund,
            latest.TotalElectricitySupplied,
            latest.ExemptSupplyOutsideUK,
            latest.ExemptSupplyEII,
        )

        if not revenue:
            revenue = latest.InflatedLevelisationFund

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
            ChargeRestrictionPeriod1=latest.ChargeRestrictionPeriod1,
            ChargeRestrictionPeriod2=latest.ChargeRestrictionPeriod2,
            LookupPeriod=latest.LookupPeriod,
            InflatedLevelisationFund=latest.InflatedLevelisationFund,
            TotalElectricitySupplied=latest.TotalElectricitySupplied,
            ExemptSupplyOutsideUK=latest.ExemptSupplyOutsideUK,
            ExemptSupplyEII=latest.ExemptSupplyEII,
        )

    @classmethod
    def calculate_feed_in_tariff_rate(
        cls,
        InflatedLevelisationFund: float,
        TotalElectricitySupplied: float,
        ExemptSupplyOutsideUK: float,
        ExemptSupplyEII: float,
    ) -> float:
        """Calculate Feed-in Tariff rate from given values."""
        return InflatedLevelisationFund / (
            TotalElectricitySupplied - ExemptSupplyOutsideUK - ExemptSupplyEII
        )
