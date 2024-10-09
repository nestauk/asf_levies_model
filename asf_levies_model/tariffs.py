import pandas as pd


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

    def __str__(self):
        """String representation of tariff name."""
        return f"{self.name}"

    def __repr__(self):
        """Representation of tariff name and fuel."""
        return f'{type(self).__name__}(name="{self.name}", fuel="{self.fuel}")'


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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
    ) -> "ElectricityStandardCredit":
        """Create ElectricityStandardCredit tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="Standard Credit. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity Standard Credit",
            fuel="electricity",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=None,
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=None,
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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
    ) -> "GasStandardCredit":
        """Create GasStandardCredit tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="Standard Credit. Gas",
            short_name="Gas Standard Credit",
            fuel="gas",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=None,
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=None,
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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
    ) -> "ElectricityOtherPayment":
        """Create ElectricityOtherPayment tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="Other Payment Method. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity Other Payment",
            fuel="electricity",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=nil_latest["Levelisation "],
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=typical_latest["Levelisation "],
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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
    ) -> "GasOtherPayment":
        """Create GasOtherPayment tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="Other Payment Method. Gas",
            short_name="Gas Other Payment",
            fuel="gas",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=nil_latest["Levelisation "],
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=typical_latest["Levelisation "],
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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 2.7,
    ) -> "ElectricityPPM":
        """Create ElectricityPPM tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 2.7 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="PPM. Electricity Single-Rate Metering Arrangement",
            short_name="Electricity PPM",
            fuel="electricity",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=nil_latest["Levelisation "],
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=typical_latest["Levelisation "],
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
        )

    @classmethod
    def from_dataframe(
        cls,
        nil_df: pd.DataFrame,
        typical_df: pd.DataFrame,
        typical_consumption: float = 11.5,
    ) -> "GasPPM":
        """Create GasPPM tariff instance from dataframe input.

        `nil_df` and `typical_df` are tidy data tables derived from ofgem annex 9 using functions in \
`asf_levies_model.getters.load_data`.

        Uses a `typical_consumption` value (default: 11.5 MWh) to create unit rates from typical_df input.

        Args:
            nil_df: a dataframe with values for nil consumption.
            typical_df: a dataframe with values for typical consumption.
            typical_consumption: float, the typical consumption value used in `typical_df`.
        """
        # Get latest values from nil and typical dfs.
        nil_latest = (
            nil_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Nil consumption")
            .loc[:, "value"]
        )
        typical_latest = (
            typical_df.loc[
                lambda df: df["28AD_Charge_Restriction_Period_start"]
                == df["28AD_Charge_Restriction_Period_start"].max()
            ]
            .set_index("Typical consumption")
            .loc[:, "value"]
        )

        # Get unit costs per MWh
        typical_latest = (typical_latest - nil_latest.fillna(0)) / typical_consumption

        return cls(
            name="PPM. Gas",
            short_name="Gas PPM",
            fuel="gas",
            df_nil=nil_latest["DF"],
            cm_nil=nil_latest["CM"],
            aa_nil=nil_latest["AA"],
            pc_nil=nil_latest["PC"],
            nc_nil=nil_latest["NC"],
            oc_nil=nil_latest["OC"],
            smncc_nil=nil_latest["SMNCC"],
            paac_nil=nil_latest["PAAC"],
            pap_nil=nil_latest["PAP"],
            ebit_nil=nil_latest["EBIT"],
            hap_nil=nil_latest["HAP"],
            levelisation_nil=nil_latest["Levelisation "],
            df=typical_latest["DF"],
            cm=typical_latest["CM"],
            aa=typical_latest["AA"],
            pc=typical_latest["PC"],
            nc=typical_latest["NC"],
            oc=typical_latest["OC"],
            smncc=typical_latest["SMNCC"],
            paac=typical_latest["PAAC"],
            pap=typical_latest["PAP"],
            ebit=typical_latest["EBIT"],
            hap=typical_latest["HAP"],
            levelisation=typical_latest["Levelisation "],
        )
