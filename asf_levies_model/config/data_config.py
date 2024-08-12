import pandera as pa

RO_schema = {
    "UpdateDate": pa.Column(str),
    "SchemeYear": pa.Column(str),
    "ObligationLevel": pa.Column(float, pa.Check.gt(0), nullable=True),
    "BuyOutPriceSchemeYear": pa.Column(float, pa.Check.gt(0), nullable=True),
    "BuyOutPricePreviousYear": pa.Column(float, pa.Check.gt(0), nullable=True),
    "ForecastAnnualRPIPreviousYear": pa.Column(
        float, [pa.Check.gt(0), pa.Check.lt(100)], nullable=True
    ),
}


WHD_schema = {
    "UpdateDate": pa.Column(str),
    "SchemeYear": pa.Column(str),
    "TargetSpendingForSchemeYear": pa.Column(float, pa.Check.gt(0), nullable=True),
    "CoreSpending": pa.Column(float, pa.Check.ge(0), nullable=True),
    "NoncoreSpending": pa.Column(float, pa.Check.ge(0), nullable=True),
    "ObligatedSuppliersCustomerBase": pa.Column(float, pa.Check.gt(0), nullable=True),
    "CompulsorySupplierFractionOfCoreGroup": pa.Column(
        float, [pa.Check.gt(0), pa.Check.le(1)], nullable=True
    ),
}

ECO_schema = {
    "UpdateDate": pa.Column(str),
    "SchemeYear": pa.Column(str),
    "AnnualisedCostECO4Gas": pa.Column(float, pa.Check.ge(0), nullable=True),
    "AnnualisedCostECO4Electricity": pa.Column(float, pa.Check.ge(0), nullable=True),
    "AnnualisedCostGBISGas": pa.Column(float, pa.Check.ge(0), nullable=True),
    "AnnualisedCostGBISElectricity": pa.Column(float, pa.Check.ge(0), nullable=True),
    "GDPDeflatorToCurrentPricesECO4": pa.Column(
        float, [pa.Check.ge(0), pa.Check.le(100)], nullable=True
    ),
    "GDPDeflatorToCurrentPricesGBIS": pa.Column(
        float, [pa.Check.ge(0), pa.Check.le(100)], nullable=True
    ),
    "FullyObligatedShareOfObligatedSupplierSupplyGas": pa.Column(
        float, [pa.Check.ge(0), pa.Check.le(1)], nullable=True
    ),
    "FullyObligatedShareOfObligatedSupplierSupplyElectricity": pa.Column(
        float, [pa.Check.ge(0), pa.Check.le(1)], nullable=True
    ),
    "ObligatedSupplierVolumeGas": pa.Column(float, pa.Check.ge(0), nullable=True),
    "ObligatedSupplierVolumeElectricity": pa.Column(
        float, pa.Check.ge(0), nullable=True
    ),
}

AAHEDC_schema = {
    "UpdateDate": pa.Column(str),
    "SchemeYear": pa.Column(str),
    "TariffCurrentYear": pa.Column(float, pa.Check.ge(0), nullable=True),
    "TariffPreviousYear": pa.Column(float, pa.Check.ge(0), nullable=True),
    "ForecastAnnualRPIPreviousYear": pa.Column(
        float, [pa.Check.ge(0), pa.Check.lt(100)], nullable=True
    ),
}

GGL_schema = {
    "UpdateDate": pa.Column(str),
    "SchemeYear": pa.Column(str),
    "LevyRate": pa.Column(float, pa.Check.ge(0), nullable=True),
    "BackdatedLevyRate": pa.Column(float, pa.Check.ge(0), nullable=True),
}

FIT_schema = {
    "ChargeRestrictionPeriod1": pa.Column(str),
    "ChargeRestrictionPeriod2": pa.Column(str),
    "LookupPeriod": pa.Column(str),
    "InflatedLevelisationFund": pa.Column(float, pa.Check.ge(0), nullable=True),
    "TotalElectricitySupplied": pa.Column(float, pa.Check.ge(0), nullable=True),
    "ExemptSupplyOutsideUK": pa.Column(float, pa.Check.ge(0), nullable=True),
    "ExemptSupplyEII": pa.Column(float, pa.Check.ge(0), nullable=True),
}

tariff_components_without_levelisation_schema = {
    "TimePeriod": pa.Column(str),
    "DirectFuel": pa.Column(float, pa.Check.ge(0), nullable=True),
    "CapacityMarket": pa.Column(float, pa.Check.ge(0), nullable=True),
    "AdjustmentAllowance": pa.Column(float, pa.Check.ge(0), nullable=True),
    "PolicyCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "NetworkCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "OperatingCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "SmartMeteringNetCostChange": pa.Column(float, nullable=True),
    "PaymentAdjustmentAdditionalCost": pa.Column(float, pa.Check.ge(0), nullable=True),
    "PaymentAdjustmentPercentage": pa.Column(float, pa.Check.ge(0), nullable=True),
    "EarningsBeforeInterestAndTaxes": pa.Column(float, pa.Check.ge(0), nullable=True),
    "HeadroomAllowancePercentage": pa.Column(float, pa.Check.ge(0), nullable=True),
}

tariff_components_schema_with_levelisation_schema = {
    "TimePeriod": pa.Column(str),
    "DirectFuel": pa.Column(float, pa.Check.ge(0), nullable=True),
    "CapacityMarket": pa.Column(float, pa.Check.ge(0), nullable=True),
    "AdjustmentAllowance": pa.Column(float, pa.Check.ge(0), nullable=True),
    "PolicyCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "NetworkCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "OperatingCosts": pa.Column(float, pa.Check.ge(0), nullable=True),
    "SmartMeteringNetCostChange": pa.Column(float, nullable=True),
    "PaymentAdjustmentAdditionalCost": pa.Column(float, pa.Check.ge(0), nullable=True),
    "PaymentAdjustmentPercentage": pa.Column(float, pa.Check.ge(0), nullable=True),
    "EarningsBeforeInterestAndTaxes": pa.Column(float, pa.Check.ge(0), nullable=True),
    "HeadroomAllowancePercentage": pa.Column(float, pa.Check.ge(0), nullable=True),
    "Levelisation": pa.Column(float, pa.Check.ge(0), nullable=True),
}

typical_consumption_values_schema = {
    "AnnualConsumptionProfile": pa.Column(str),
    "ElectricitySingleRatekWh": pa.Column(float, pa.Check.ge(0)),
    "ElectricityMultiRegisterkWh": pa.Column(float, pa.Check.ge(0)),
    "GaskWh": pa.Column(float, pa.Check.ge(0)),
}

ofgem_archetypes_schema = {
    "NumberOfHouseholds": pa.Column(float),
    "MainHeatingFuel": pa.Column(str),
    "GrossAnnualHouseholdIncome£": pa.Column(float),
    "AverageAnnualElecConsumptionkWh": pa.Column(float),
    "AverageAnnualGasConsumptionkWh": pa.Column(float),
}
