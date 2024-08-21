import copy
import numpy as np


class Levy:
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
    ):
        self.name = name
        self.short_name = short_name

        # Mode split
        self.electricity_weight = electricity_weight
        self.gas_weight = gas_weight
        self.tax_weight = tax_weight

        # Levy method
        self.variable_weight = variable_weight
        self.fixed_weight = fixed_weight

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
        electricity_consumption,
        gas_consumption,
        electricity_customer,
        gas_customer,
    ):
        return self.calculate_variable_levy(
            electricity_consumption, gas_consumption
        ) + self.calculate_fixed_levy(electricity_customer, gas_customer)

    def calculate_variable_levy(self, electricity_consumption, gas_consumption):
        return (
            self.electricity_variable_rate * electricity_consumption
            + self.gas_variable_rate * gas_consumption
        )

    def calculate_fixed_levy(self, electricity_customer, gas_customer):
        return (self.electricity_fixed_rate * electricity_customer) + (
            self.gas_fixed_rate * gas_customer
        )

    def rebalance_levy(
        self,
        new_electricity_weight,
        new_gas_weight,
        new_tax_weight,
        new_variable_weight,
        new_fixed_weight,
        supply_gas,
        supply_elec,
        customers_gas,
        customers_elec,
        inplace=False,
    ):

        # Revenue contributions
        revenue_gas = self.revenue * new_gas_weight
        revenue_elec = self.revenue * new_electricity_weight
        revenue_tax = self.revenue * new_tax_weight

        # New variable levy rate
        new_levy_var_gas = (revenue_gas / supply_gas) * new_variable_weight
        new_levy_var_elec = (revenue_elec / supply_elec) * new_variable_weight

        # New fixed levy rate
        new_levy_fixed_gas = (revenue_gas / customers_gas) * new_fixed_weight
        new_levy_fixed_elec = (revenue_elec / customers_elec) * new_fixed_weight

        if not self._is_revenue_maintained(
            new_levy_var_gas,
            new_levy_var_elec,
            new_levy_fixed_gas,
            new_levy_fixed_elec,
            supply_gas,
            supply_elec,
            customers_gas,
            customers_elec,
            self.revenue,
        ):
            raise ValueError("Rebalancing failed to maintain revenue.")

        if inplace:
            # Update attributes
            self.electricity_weight = new_electricity_weight
            self.gas_weight = new_gas_weight
            self.tax_weight = new_tax_weight

            self.variable_weight = new_variable_weight
            self.fixed_weight = new_fixed_weight

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

            new_levy.variable_weight = new_variable_weight
            new_levy.fixed_weight = new_fixed_weight

            new_levy.electricity_variable_rate = new_levy_var_elec
            new_levy.electricity_fixed_rate = new_levy_fixed_elec
            new_levy.gas_variable_rate = new_levy_var_gas
            new_levy.gas_fixed_rate = new_levy_fixed_gas
            new_levy.general_taxation = revenue_tax
            return new_levy

    @staticmethod
    def _is_revenue_maintained(
        new_levy_var_gas,
        new_levy_var_elec,
        new_levy_fixed_gas,
        new_levy_fixed_elec,
        supply_gas,
        supply_elec,
        customers_gas,
        customers_elec,
        target_revenue,
    ):
        new_revenue_gas = (new_levy_var_gas * supply_gas) + (
            new_levy_fixed_gas * customers_gas
        )
        new_revenue_elec = (new_levy_var_elec * supply_elec) + (
            new_levy_fixed_elec * customers_elec
        )

        if abs((new_revenue_gas + new_revenue_elec) - target_revenue) < 0.01:
            return True
        else:
            return False

    def __repr__(self):
        non_zero = [
            attr
            for attr in [
                "electricity_weight",
                "gas_weight",
                "variable_weight",
                "fixed_weight",
                "electricity_variable_rate",
                "electricity_fixed_rate",
                "gas_variable_rate",
                "gas_fixed_rate",
            ]
            if getattr(self, attr) > 0
        ]

        return repr(
            f'Levy(name="{self.name}", short_name="{self.short_name}", {", ".join([f"{attr}={getattr(self, attr)}" for attr in non_zero])})'
        )

    def __str__(self):
        return str(f'Levy(name="{self.name}", short_name="{self.short_name}")')


class RO(Levy):
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        UpdateDate,
        SchemeYear,
        obligation_level,
        BuyOutPriceSchemeYear,
        BuyOutPricePreviousYear,
        ForecastAnnualRPIPreviousYear,
    ):
        super(RO, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
    def from_dataframe(cls, df, revenue=None, denominator=None):

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
            name="renewables obligation",
            short_name="ro",
            electricity_weight=1,
            gas_weight=0,
            tax_weight=0,
            variable_weight=1,
            fixed_weight=0,
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
        cls, ObligationLevel, BuyOutPriceSchemeYear, BuyOutPricePreviousYear
    ):
        return (
            ObligationLevel * BuyOutPriceSchemeYear
            if not np.isnan(BuyOutPriceSchemeYear)
            else ObligationLevel * BuyOutPricePreviousYear
        )


class AAHEDC(Levy):
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        UpdateDate,
        SchemeYear,
        TariffCurrentYear,
        TariffPreviousYear,
        ForecastAnnualRPIPreviousYear,
    ):
        super(AAHEDC, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
    def from_dataframe(cls, df, revenue=None, denominator=None):

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
            variable_weight=1,
            fixed_weight=0,
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
        cls, TariffPreviousYear, ForecastAnnualRPIPreviousYear
    ):
        return TariffPreviousYear * (1 + ForecastAnnualRPIPreviousYear / 100)

    @classmethod
    def calculate_aahedc_rate(cls, TariffCurrentYear, aahedc_tariff_forecast):
        return (
            TariffCurrentYear * 10
            if not np.isnan(TariffCurrentYear)
            else aahedc_tariff_forecast * 10
        )


class GGL(Levy):
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        UpdateDate,
        SchemeYear,
        LevyRate,
        BackdatedLevyRate,
    ):
        super(GGL, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
    def from_dataframe(cls, df, revenue=None, denominator=None):

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
            variable_weight=0,
            fixed_weight=1,
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
    def calculate_ggl_rate(cls, LevyRate, BackdatedLevyRate):
        return (
            (LevyRate * 365 / 100)
            if np.isnan(BackdatedLevyRate)
            else (LevyRate * 365 / 100) + (BackdatedLevyRate * 122 / 100)
        )


class WHD(Levy):
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        UpdateDate,
        SchemeYear,
        TargetSpendingForSchemeYear,
        CoreSpending,
        NoncoreSpending,
        ObligatedSuppliersCustomerBase,
        CompulsorySupplierFractionOfCoreGroup,
    ):
        super(WHD, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
            variable_weight=0,
            fixed_weight=1,
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
        TargetSpendingForSchemeYear,
        CoreSpending,
        NoncoreSpending,
        ObligatedSuppliersCustomerBase,
        CompulsorySupplierFractionOfCoreGroup,
    ):
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
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        UpdateDate,
        SchemeYear,
        AnnualisedCostECO4Gas,
        AnnualisedCostECO4Electricity,
        AnnualisedCostGBISGas,
        AnnualisedCostGBISElectricity,
        GDPDeflatorToCurrentPricesECO4,
        GDPDeflatorToCurrentPricesGBIS,
        FullyObligatedShareOfObligatedSupplierSupplyGas,
        FullyObligatedShareOfObligatedSupplierSupplyElectricity,
        ObligatedSupplierVolumeGas,
        ObligatedSupplierVolumeElectricity,
    ):
        super(ECO, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
    def from_dataframe(cls, df, revenue=None):

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
            variable_weight=1,
            fixed_weight=0,
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
        AnnualisedCostECO4,
        AnnualisedCostGBIS,
        GDPDeflatorToCurrentPricesECO4,
        GDPDeflatorToCurrentPricesGBIS,
        FullyObligatedShareOfObligatedSupplierSupply,
        ObligatedSupplierVolume,
    ):
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
    def __init__(
        self,
        name,
        short_name,
        electricity_weight,
        gas_weight,
        tax_weight,
        variable_weight,
        fixed_weight,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        general_taxation,
        revenue,
        ChargeRestrictionPeriod1,
        ChargeRestrictionPeriod2,
        LookupPeriod,
        InflatedLevelisationFund,
        TotalElectricitySupplied,
        ExemptSupplyOutsideUK,
        ExemptSupplyEII,
    ):
        super(FIT, self).__init__(
            name,
            short_name,
            electricity_weight,
            gas_weight,
            tax_weight,
            variable_weight,
            fixed_weight,
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
    def from_dataframe(cls, df, revenue=None):

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
            variable_weight=1,
            fixed_weight=0,
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
        InflatedLevelisationFund,
        TotalElectricitySupplied,
        ExemptSupplyOutsideUK,
        ExemptSupplyEII,
    ):
        return InflatedLevelisationFund / (
            TotalElectricitySupplied - ExemptSupplyOutsideUK - ExemptSupplyEII
        )
