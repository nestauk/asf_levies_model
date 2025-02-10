import pandas as pd
import copy
from typing import Union, Optional

from asf_levies_model.levies import LevyCollection
from asf_levies_model.utils.utils import PriceCapPeriod


class Tariff:
    """A generic tariff object.

        Intended primarily as a parent class for specific tariffs, but can be used as
    a general tariff object for prototyping.

        Attributes:
            name: str, the full name of a tariff.
            short_name: str, the abbreviated name for a tariff.
            fuel: str, the tariff fuel type, assumed gas or electricity.
            df_nil: float, direct fuel cost (nil consumption).
            cm_nil: float, capacity market cost (nil consumption).
            aa_nil: float, adjustment allowance (nil consumption).
            pc_nil: float, policy cost (nil consumption).
            nc_nil: float, network cost (nil consumption).
            oc_nil: float, operating cost (nil consumption).
            smncc_nil: float, smart metering net cost change (nil consumption).
            paac_nil: float, payment method additional administrative cost (nil consumption).
            pap_nil: float, payment method adjustment percentage (nil consumption).
            ebit_nil: float, earnings before interest and tax (EBIT) allowance (nil consumption).
            hap_nil: float, headroom allowance percentage (nil consumption).
            levelisation_nil: float, levelisation (nil consumption).
            df: float, direct fuel cost.
            cm: float, capacity market cost.
            aa: float, adjustment allowance.
            pc: float, policy cost.
            nc: float, network cost.
            oc: float, operating cost.
            smncc: float, smart metering net cost change.
            paac: float, payment method additional administrative cost.
            pap: float, payment method adjustment percentage.
            ebit: float, earnings before interest and tax (EBIT) allowance.
            hap: float, headroom allowance percentage.
            levelisation: float, levelisation.
            price_cap_period: Interval, price cap period covered by tariff instance.
    """

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        """Initializes the instance based on provided tariff parameters.

        Args:
            name: str, the full name of a tariff.
            short_name: str, the abbreviated name for a tariff.
            fuel: str, the tariff fuel type, assumed gas or electricity.
            df_nil: float, direct fuel cost (nil consumption).
            cm_nil: float, capacity market cost (nil consumption).
            aa_nil: float, adjustment allowance (nil consumption).
            pc_nil: float, policy cost (nil consumption).
            nc_nil: float, network cost (nil consumption).
            oc_nil: float, operating cost (nil consumption).
            smncc_nil: float, smart metering net cost change (nil consumption).
            paac_nil: float, payment method additional administrative cost (nil consumption).
            pap_nil: float, payment method adjustment percentage (nil consumption).
            ebit_nil: float, earnings before interest and tax (EBIT) allowance (nil consumption).
            hap_nil: float, headroom allowance percentage (nil consumption).
            levelisation_nil: float, levelisation (nil consumption).
            df: float, direct fuel cost.
            cm: float, capacity market cost.
            aa: float, adjustment allowance.
            pc: float, policy cost.
            nc: float, network cost.
            oc: float, operating cost.
            smncc: float, smart metering net cost change.
            paac: float, payment method additional administrative cost.
            pap: float, payment method adjustment percentage.
            ebit: float, earnings before interest and tax (EBIT) allowance.
            hap: float, headroom allowance percentage.
            levelisation: float, levelisation.
            price_cap_period: Interval, price cap period covered by tariff instance.
        """
        self.name = name
        self.short_name = short_name
        self.fuel = fuel
        self.df_nil = df_nil
        self.cm_nil = cm_nil
        self.aa_nil = aa_nil
        self.pc_nil = pc_nil
        self.nc_nil = nc_nil
        self.oc_nil = oc_nil
        self.smncc_nil = smncc_nil
        self.paac_nil = paac_nil
        self.pap_nil = pap_nil
        self.ebit_nil = ebit_nil
        self.hap_nil = hap_nil
        self.levelisation_nil = levelisation_nil
        self.df = df
        self.cm = cm
        self.aa = aa
        self.pc = pc
        self.nc = nc
        self.oc = oc
        self.smncc = smncc
        self.paac = paac
        self.pap = pap
        self.ebit = ebit
        self.hap = hap
        self.levelisation = levelisation
        self.price_cap_period = price_cap_period

    def calculate_nil_consumption(self) -> float:
        """Calculate value for nil consumption tariff component."""
        return sum(
            [
                component
                for component in [
                    self.df_nil,
                    self.cm_nil,
                    self.aa_nil,
                    self.pc_nil,
                    self.nc_nil,
                    self.oc_nil,
                    self.smncc_nil,
                    self.paac_nil,
                    self.pap_nil,
                    self.ebit_nil,
                    self.hap_nil,
                    self.levelisation_nil,
                ]
                if not pd.isna(component)
            ]
        )

    def calculate_variable_consumption(self, consumption: float) -> float:
        """Calculate value for variable tariff component, given consumption value."""
        return sum(
            [
                component * consumption
                for component in [
                    self.df,
                    self.cm,
                    self.aa,
                    self.pc,
                    self.nc,
                    self.oc,
                    self.smncc,
                    self.paac,
                    self.pap,
                    self.ebit,
                    self.hap,
                    self.levelisation,
                ]
                if not pd.isna(component)
            ]
        )

    def calculate_total_consumption(self, consumption: float, vat: bool = False):
        """Calculate total price of tariff at given consumption value.

        Zero consumption assumed to indicate off-gas. If you want the standing charge only \
use the calculate_nil_consumption method.

        Args:
            consumption: float, fuel consumption in MWh.
            vat: bool, whether to add VAT at 5%, default: False.
        """
        return (
            (self.calculate_nil_consumption() if consumption > 0 else 0)
            + self.calculate_variable_consumption(consumption)
        ) * (1.05 if vat else 1.0)

    def update_policy_costs(
        self, levy_collection: LevyCollection, inplace: bool = False
    ) -> Optional["Tariff"]:
        """Updates the policy costs pc and pc_nil according to passed LevyCollection.

        Args:
            levy_collection: LevyCollection to use for updating.
            inplace: Whether to update in place, default False.
        """
        if inplace:
            if self.fuel == "electricity":
                self.pc_nil = levy_collection.calculate_fixed_levies(True, False)
                self.pc = levy_collection.calculate_variable_levies(1.0, 0.0)
            elif self.fuel == "gas":
                self.pc_nil = levy_collection.calculate_fixed_levies(False, True)
                self.pc = levy_collection.calculate_variable_levies(0.0, 1.0)
            else:
                raise ValueError(
                    f"Can't update policy costs where fuel is: {self.fuel}, fuel expected to be 'gas' or 'electricity'."
                )
            return None
        else:
            new_tariff = self.copy(deep=True)
            if self.fuel == "electricity":
                new_tariff.pc_nil = levy_collection.calculate_fixed_levies(True, False)
                new_tariff.pc = levy_collection.calculate_variable_levies(1.0, 0.0)
            elif self.fuel == "gas":
                new_tariff.pc_nil = levy_collection.calculate_fixed_levies(False, True)
                new_tariff.pc = levy_collection.calculate_variable_levies(0.0, 1.0)
            else:
                raise ValueError(
                    f"Can't update policy costs where fuel is: {self.fuel}, fuel expected to be 'gas' or 'electricity'."
                )
            return new_tariff

    def copy(self, deep: bool = True) -> "Tariff":
        """Create copy of self."""
        if deep:
            return copy.deepcopy(self)
        else:
            return copy.copy(self)

    def __str__(self):
        """String representation of tariff name."""
        return f'{self.name}, price cap period= "{repr(self.price_cap_period)}"'

    def __repr__(self):
        """Representation of tariff name and fuel."""
        return f'{type(self).__name__}(name="{self.name}", fuel="{self.fuel}", price cap period= "{repr(self.price_cap_period)}")'


class ElectricityStandardCredit(Tariff):
    """Electricity Standard Credit Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(ElectricityStandardCredit, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
        price_cap: str = "LATEST",
    ) -> "ElectricityStandardCredit":
        """Create ElectricityStandardCredit tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap: str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="Standard Credit. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity Standard Credit",
            fuel="electricity",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=None,
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=None,
            price_cap_period=price_cap_date,
        )


class GasStandardCredit(Tariff):
    """Gas Standard Credit Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(GasStandardCredit, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
        price_cap: str = "LATEST",
    ) -> "GasStandardCredit":
        """Create GasStandardCredit tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap: str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="Standard Credit. Gas",
            short_name="Gas Standard Credit",
            fuel="gas",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=None,
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=None,
            price_cap_period=price_cap_date,
        )


class ElectricityOtherPayment(Tariff):
    """Electricity Other Payment Method Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(ElectricityOtherPayment, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
        price_cap: str = "LATEST",
    ) -> "ElectricityOtherPayment":
        """Create ElectricityOtherPayment tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap: str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="Other Payment Method. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity Other Payment",
            fuel="electricity",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=nil_df["Levelisation "],
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=typical_df["Levelisation "],
            price_cap_period=price_cap_date,
        )


class GasOtherPayment(Tariff):
    """Gas Other Payment Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(GasOtherPayment, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
        price_cap: str = "LATEST",
    ) -> "GasOtherPayment":
        """Create GasOtherPayment tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap:str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="Other Payment Method. Gas",
            short_name="Gas Other Payment",
            fuel="gas",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=nil_df["Levelisation "],
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=typical_df["Levelisation "],
            price_cap_period=price_cap_date,
        )


class ElectricityPPM(Tariff):
    """Electricity PPM Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(ElectricityPPM, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
        price_cap: str = "LATEST",
    ) -> "ElectricityPPM":
        """Create ElectricityPPM tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap:str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="PPM. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity PPM",
            fuel="electricity",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=nil_df["Levelisation "],
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=typical_df["Levelisation "],
            price_cap_period=price_cap_date,
        )


class GasPPM(Tariff):
    """Gas PPM Tariff.\n"""

    __doc__ += (
        Tariff.__doc__.split("\n", maxsplit=4)[4]
        + """\
"""
    )

    def __init__(
        self,
        name: str,
        short_name: str,
        fuel: str,
        df_nil: float,
        cm_nil: float,
        aa_nil: float,
        pc_nil: float,
        nc_nil: float,
        oc_nil: float,
        smncc_nil: float,
        paac_nil: float,
        pap_nil: float,
        ebit_nil: float,
        hap_nil: float,
        levelisation_nil: float,
        df: float,
        cm: float,
        aa: float,
        pc: float,
        nc: float,
        oc: float,
        smncc: float,
        paac: float,
        pap: float,
        ebit: float,
        hap: float,
        levelisation: float,
        price_cap_period: Union[pd.Interval, "PriceCapPeriod"],
    ) -> None:
        super(GasPPM, self).__init__(
            name,
            short_name,
            fuel,
            df_nil,
            cm_nil,
            aa_nil,
            pc_nil,
            nc_nil,
            oc_nil,
            smncc_nil,
            paac_nil,
            pap_nil,
            ebit_nil,
            hap_nil,
            levelisation_nil,
            df,
            cm,
            aa,
            pc,
            nc,
            oc,
            smncc,
            paac,
            pap,
            ebit,
            hap,
            levelisation,
            price_cap_period,
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
        price_cap: str = "LATEST",
    ) -> "GasPPM":
        """Create GasPPM tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
            price_cap:str, the price cap period to return, default: LATEST.
        """
        # Get latest values from nil and typical dfs.
        if price_cap == "LATEST":
            nil_price_cap = nil_df.index.max()[1]
            nil_df = (
                nil_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(nil_price_cap) else False
                    )
                ]
                .set_index("Nil consumption")
                .loc[:, "value"]
            )

            typical_price_cap = typical_df.index.max()[1]
            typical_df = (
                typical_df.loc[
                    lambda df: df.index.map(
                        lambda x: True if x[1].overlaps(typical_price_cap) else False
                    )
                ]
                .set_index("Typical consumption")
                .loc[:, "value"]
            )

            assert nil_price_cap == typical_price_cap
            price_cap_date = PriceCapPeriod(
                left=nil_price_cap.left, right=nil_price_cap.right, closed="both"
            )
        else:
            # Otherwise assume you've got a provided date
            price_cap_date = pd.to_datetime(price_cap)
            nil_mask = nil_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()
            typical_mask = typical_df.index.map(
                lambda x: True if price_cap_date in x[1] else False
            ).to_numpy()

            price_cap_date = nil_df.index[
                nil_df.index.map(lambda x: True if price_cap_date in x[1] else False)
            ].unique()[0][1]

            price_cap_date = PriceCapPeriod(
                left=price_cap_date.left, right=price_cap_date.right, closed="both"
            )

            if (nil_mask.sum() == 0) | (typical_mask.sum() == 0):
                raise IndexError(f"Price cap data {price_cap} not found in index.")
            else:
                nil_df = (
                    nil_df.loc[nil_mask].set_index("Nil consumption").loc[:, "value"]
                )
                typical_df = (
                    typical_df.loc[typical_mask]
                    .set_index("Typical consumption")
                    .loc[:, "value"]
                )

        # Get unit costs per MWh
        typical_df = (typical_df - nil_df.fillna(0)) / typical_consumption

        return cls(
            name="PPM. Gas",
            short_name="Gas PPM",
            fuel="gas",
            df_nil=nil_df["DF"],
            cm_nil=nil_df["CM"],
            aa_nil=nil_df["AA"],
            pc_nil=nil_df["PC"],
            nc_nil=nil_df["NC"],
            oc_nil=nil_df["OC"],
            smncc_nil=nil_df["SMNCC"],
            paac_nil=nil_df["PAAC"],
            pap_nil=nil_df["PAP"],
            ebit_nil=nil_df["EBIT"],
            hap_nil=nil_df["HAP"],
            levelisation_nil=nil_df["Levelisation "],
            df=typical_df["DF"],
            cm=typical_df["CM"],
            aa=typical_df["AA"],
            pc=typical_df["PC"],
            nc=typical_df["NC"],
            oc=typical_df["OC"],
            smncc=typical_df["SMNCC"],
            paac=typical_df["PAAC"],
            pap=typical_df["PAP"],
            ebit=typical_df["EBIT"],
            hap=typical_df["HAP"],
            levelisation=typical_df["Levelisation "],
            price_cap_period=price_cap_date,
        )
