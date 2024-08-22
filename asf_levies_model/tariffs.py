import pandas as pd


class Tariff:
    def __init__(
        self,
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
    ):
        self.name = name
        self.short_name = (short_name,)
        self.fuel = fuel
        self.df_nil = df_nil  # Direct Fuel Cost (Nil consumption)
        self.cm_nil = cm_nil  # Capacity Market Cost (Nil consumption)
        self.aa_nil = aa_nil  # Adjustment Allowance (Nil consumption)
        self.pc_nil = pc_nil  # Policy Cost (Nil consumption)
        self.nc_nil = nc_nil  # Network Cost (Nil consumption)
        self.oc_nil = oc_nil  # Operating Cost (Nil consumption)
        self.smncc_nil = smncc_nil  # Smart Metering Net Cost Change (Nil consumption)
        self.paac_nil = (
            paac_nil  # Payment Method Additional Administrative Cost (Nil consumption)
        )
        self.pap_nil = pap_nil  # Payment Method Adjustment Percentage (Nil consumption)
        self.ebit_nil = ebit_nil  # Earnings Before Interest and Tax (EBIT) Allowance (Nil consumption)
        self.hap_nil = hap_nil  # Headroom Allowance Percentage (Nil consumption)
        self.levelisation_nil = levelisation_nil  # Levelisation (Nil consumption)
        self.df = df  # Direct Fuel Cost
        self.cm = cm  # Capacity Market Cost
        self.aa = aa  # Adjustment Allowance
        self.pc = pc  # Policy Cost
        self.nc = nc  # Network Cost
        self.oc = oc  # Operating Cost
        self.smncc = smncc  # Smart Metering Net Cost Change
        self.paac = paac  # Payment Method Additional Administrative Cost
        self.pap = pap  # Payment Method Adjustment Percentage
        self.ebit = ebit  # Earnings Before Interest and Tax (EBIT) Allowance
        self.hap = hap  # Headroom Allowance Percentage
        self.levelisation = levelisation  # Levelisation

    def calculate_nil_consumption(self):
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

    def calculate_variable_consumption(self, consumption):
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

    def calculate_total_consumption(self, consumption, vat=False):
        return (
            self.calculate_nil_consumption()
            + self.calculate_variable_consumption(consumption)
        ) * (1.05 if vat else 1.0)

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f'{type(self).__name__}(name="{self.name}", fuel="{self.fuel}")'


class ElectricityStandardCredit(Tariff):
    def __init__(
        self,
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
    ):
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
    def from_dataframe(cls, nil_df, typical_df, typical_consumption=2.7):

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
    def __init__(
        self,
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
    ):
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
    def from_dataframe(cls, nil_df, typical_df, typical_consumption=11.5):

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
