import pandas as pd


class Consumer:
    """
    Represents a single energy consumer that pays gas and/or electricity bills.

    Attributes:
        name: The name of the energy consumer, e.g., Ofgem consumer archetype name.
        net_annual_income: The average net annual income of represented consumer, in £.
        net_income_decile: The income decile that the consumer's net annual income falls in.
        main_heating_fuel: The name of the consumer's main heating fuel.
        gas_consumption: Annual gas consumption, in MWh.
        electricity_consumption: Annual electricity consumption, in MWh.
        gas_tariff: Tariff object to be used to calculate the consumer's gas bill.
        electricity_tariff: Tariff object to be used to calculate the consumer's electricity bill.
        unmetered_fuel_spend: Annual amount spent on unmetered fuel (i.e., fuel that is not gas or electricity), in £.
        scheme_eligible: Eligibilty for social support scheme.

    Properties:
        unit_cost_ratio: Electricity to gas unit cost ratio, considering any unit discounts from social support.
        fuel_poverty_gap: Difference between total fuel spend and threshold of 10% of net annual income, in £.
        electricity_subtotal_bill: Electricity subtotal bill, including VAT, before any social support adjustment, in £.
        gas_subtotal_bill: Gas subtotal bill, including VAT, before any social support adjustment, in £.
        electricity_bill: Electricity final bill, including VAT, after any social support adjustment, in £.
        gas_bill: Gas final bill, including VAT, after any social support adjustment, in £.
        dual_fuel_bill: Combined electricity and gas final bill, including VAT, after any social support adjustment, in £.

    Methods:
        apply_social_support_adjustment():
            Overwrites the electricity or gas bill property with an updated value reflected a social support adjustment (discount or additional cost).
        get_tidy_summary():
            Returns a dataframe containing all public instance attributes and properties, except name which has a dedicated column.
        consumer_from_dataframe():
            Creates a Consumer instance from a dataframe input.
        boiler_to_hp_savings():
            Returns a cost savings estimate if consumer is assumed to switch from a gas boiler for heat to an electric heat pump.
    """

    def __init__(
        self,
        name: str,
        archetype: str,
        net_annual_income: float,
        net_income_decile: int,
        main_heating_fuel: str,
        gas_consumption: float,
        electricity_consumption: float,
        gas_tariff: object,
        electricity_tariff: object,
        unmetered_fuel_spend: float = 0,
        scheme_eligible: bool = False,
        size: int = 0,
    ) -> None:
        """Initalizes a Consumer instance based on provided parameters.

        Parameters
        ----------
        name : str
            Unique name of the energy consumer.
        archetype : str
            Name of broader archetype the consumer belongs to.
        net_annual_income : float
            The average net annual income of represented consumer, in £.
        net_income_decile : int
            The income decile that the consumer's net annual income falls in.
        main_heating_fuel : str
            The name of the consumer's main heating fuel.
        gas_consumption : float
            Annual gas consumption, in MWh.
        electricity_consumption : float
            Annual electricity consumption, in MWh.
        gas_tariff : object
            Tariff object to be used to calculate the consumer's gas bill.
        electricity_tariff : object
            Tariff object to be used to calculate the consumer's electricity bill.
        unmetered_fuel_spend : float, optional
            Annual amount spent on unmetered fuel (i.e., fuel that is not gas or electricity), in £, by default 0.
        scheme_eligible : bool, optional
            Eligibilty for social support scheme, by default False.
        size : int, optional
            Number of households in consumer profile, by default 0 (i.e. size is not considered).
        """

        self.name = name
        self.archetype = archetype
        self.net_annual_income = net_annual_income
        self.net_income_decile = net_income_decile
        self.main_heating_fuel = main_heating_fuel
        self.gas_consumption = gas_consumption
        self.electricity_consumption = electricity_consumption
        self.scheme_eligible = scheme_eligible
        self.unmetered_fuel_spend = unmetered_fuel_spend
        self.size = size

        self.electricity_tariff = electricity_tariff
        self.gas_tariff = gas_tariff

        self._electricity_bill = None
        self._gas_bill = None

        self._adjustment_mode = None

    @property
    def unit_cost_ratio(self) -> float:
        if self._adjustment_mode == "unit discount":
            unit_discount_electricity = (
                self.electricity_subtotal_bill - self.electricity_bill
            ) / self.electricity_consumption
            unit_discount_gas = (
                self.gas_subtotal_bill - self.gas_bill
            ) / self.gas_consumption
        else:
            unit_discount_electricity = 0
            unit_discount_gas = 0

        if self.gas_consumption > 0:
            ratio = (
                self.electricity_tariff.calculate_variable_consumption(1)
                - unit_discount_electricity
            ) / (self.gas_tariff.calculate_variable_consumption(1) - unit_discount_gas)
        else:
            ratio = None

        return ratio

    @property
    def fuel_poverty_gap(self) -> float:
        """Get the fuel poverty gap estimate.

        Returns
        -------
        float
            The fuel poverty gap estimate, in £.
        """
        total_fuel_spend = (
            self.electricity_bill + self.gas_bill + self.unmetered_fuel_spend
        )
        threshold = 0.1 * self.net_annual_income
        return max(total_fuel_spend - threshold, 0)

    @property
    def electricity_subtotal_bill(self) -> float:
        """Get the electricity subtotal bill (before any social support adjustments).

        Returns
        -------
        float
            Annual electricity subtotal bill, including VAT, in £.
        """
        return self.electricity_tariff.calculate_total_consumption(
            self.electricity_consumption, vat=True
        )

    @property
    def gas_subtotal_bill(self) -> float:
        """Get the gas subtotal bill (before any social support adjustments).

        Returns
        -------
        float
            Annual gas subtotal bill, including VAT, in £.
        """
        return self.gas_tariff.calculate_total_consumption(
            self.gas_consumption, vat=True
        )

    @property
    def electricity_bill(self) -> float:
        """Get the final electricity bill (after social support adjustments, if any). If no social support is implemented, the final bill is the same as the subtotal bill.

        Returns
        -------
        float
            Annual electricity bill, including VAT, in £.
        """
        if self._electricity_bill is not None:
            return self._electricity_bill
        return self.electricity_subtotal_bill

    @electricity_bill.setter
    def electricity_bill(self, value: float) -> None:
        """Set the final electricity bill value.

        Parameters
        ----------
        value : float
            The new final electricity bill value, in £.
        """
        self._electricity_bill = value

    @property
    def gas_bill(self) -> float:
        """Get the final gas bill (after social support adjustments, if any). If no social support is implemented, the final bill is the same as the subtotal bill.

        Returns
        -------
        float
            Annual gas bill, including VAT, in £.
        """
        if self._gas_bill is not None:
            return self._gas_bill
        return self.gas_subtotal_bill

    @gas_bill.setter
    def gas_bill(self, value: float) -> None:
        """Set the final gas bill value.

        Parameters
        ----------
        value : float
            The new final gas bill value, in £.
        """
        self._gas_bill = value

    @property
    def dual_fuel_bill(self) -> float:
        """Get the combined final bill for electricity and gas (after any social support adjustment).

        Returns
        -------
        float
            Annual dual fual bill, including VAT, in £.
        """
        return self.gas_bill + self.electricity_bill

    def apply_social_support_adjustment(
        self,
        adjustment_fuel: str,
        adjustment_parameter: float,
        adjustment_mode: str,
    ) -> None:
        """Overwrites the electricity or gas bill property with an updated value reflected a social support adjustment (discount or additional cost).

        Parameters
        ----------
        adjustment_fuel : str
            Fuel bill to be adjusted, accepted strings are "electricity" and "gas".
        adjustment_parameter : float
            Value with which to adjust the fuel bill depending on adjusment mode. If adjustment mode is:
            (a) flat adjustment: Value (£) to be added to the subtotal bill.
            (b) percentage discount: Percentage (%) of subtotal bill to be subtracted.
            (c) unit discount: Value (£/MWh) to be multiplied by fuel consumption, and product subtracted from the subtotal bill.
        adjustment_mode : str
            Acceptable strings are "flat adjustment", "percentage discount" and "unit discount".

        Raises
        ------
        ValueError
            Error raised if an invalid adjustment mode is provided.
        ValueError
            Error raised if an invalid fuel type is provided.
        """
        if adjustment_fuel == "electricity":
            if adjustment_mode == "flat adjustment":
                self.electricity_bill = (
                    self.electricity_subtotal_bill + adjustment_parameter
                )
                self._adjustment_mode = adjustment_mode
            elif adjustment_mode == "percentage discount":
                self.electricity_bill = self.electricity_subtotal_bill * (
                    (100 - adjustment_parameter) / 100
                )
                self._adjustment_mode = adjustment_mode
            elif adjustment_mode == "unit discount":
                self.electricity_bill = self.electricity_subtotal_bill - (
                    self.electricity_consumption * adjustment_parameter
                )
                self._adjustment_mode = adjustment_mode
            else:
                raise ValueError(
                    "Please provide an adjustment mode from the following: flat adjustment, percentage_discount, unit discount"
                )
        elif adjustment_fuel == "gas":
            if adjustment_mode == "flat adjustment":
                self.gas_bill = self.gas_subtotal_bill + adjustment_parameter
                self._adjustment_mode = adjustment_mode
            elif adjustment_mode == "percentage discount":
                self.gas_bill = self.gas_subtotal_bill * (
                    (100 - adjustment_parameter) / 100
                )
                self._adjustment_mode = adjustment_mode
            elif adjustment_mode == "unit discount":
                self.gas_bill = self.gas_subtotal_bill - (
                    self.gas_consumption * adjustment_parameter
                )
                self._adjustment_mode = adjustment_mode
            else:
                raise ValueError(
                    "Please provide an adjustment mode from the following: flat adjustment, percentage_discount, unit discount"
                )
        else:
            raise ValueError(
                "Please specify the fuel bill to adjust (electricity or gas)."
            )

    def get_tidy_summary(self) -> pd.DataFrame:
        """Returns a dataframe containing all public attributes and properties, except name which has a dedicated column.

        Returns
        -------
        pd.DataFrame
            Dataframe with columns ["Name", "Attribute", "Value"].
        """
        attributes = [
            (key, value)
            for key, value in self.__dict__.items()
            if key != "name" and not key.startswith("_")
        ]
        properties = [
            (key, getattr(self, key))
            for key, value in self.__class__.__dict__.items()
            if isinstance(value, property)
        ]
        attributes.extend(properties)
        df = pd.DataFrame(attributes, columns=["Attribute", "Value"])
        df["Name"] = self.name
        return df[["Name", "Attribute", "Value"]]

    @classmethod
    def consumer_from_dataframe(
        cls,
        df: pd.DataFrame,
        row: int,
        name_col: str,
        archetype_col: str,
        net_annual_income_col: str,
        main_heating_fuel_col: str,
        gas_consumption_col: str,
        electricity_consumption_col: str,
        gas_tariff: object,
        electricity_tariff: object,
        net_income_decile_col: str = None,
        unmetered_fuel_spend_col: str = None,
        scheme_eligible_col: str = None,
        size_col: str = None,
        unit_converter: float = 1,
    ) -> "Consumer":
        """Creates a Consumer instance from dataframe input.

        Parameters
        ----------
        df : pd.DataFrame
            Dataframe where each row corresponds to a consumer profile and columns describe (at least) name, net annual, income, main heating fuel, annual gas consumption, annual electricity consumption.
        row : int
            Row number in dataframe for consumer profile to instantiate.
        name_col : str
            Name of the dataframe column with unique consumer name (str).
        archetype_col : str
            Name of the dataframe column with consumer profile category (str).
        net_annual_income_col : str
            Name of the dataframe column with net annual income amount (float).
        main_heating_fuel_col : str
            Name of the dataframe column with main heating fuel description (str).
        gas_consumption_col : str
            Name of the dataframe column with annual gas consumption amount (float).
        electricity_consumption_col : str
            Name of the dataframe column with annual electricity consumption amount (float).
        gas_tariff : object
            Gas tariff object for consumer bill to be calculated with.
        electricity_tariff : object
            Electricity tariff object for consumer bill to be calculated with.
        net_income_decile_col : str, optional
            Name of the dataframe column with income decile (int), by default None.
        unmetered_fuel_spend_col : str, optional
            Name of the dataframe column with annual unmetered fuel spend amount (float), by default None.
        scheme_eligible_col : str, optional
            Name of the dataframe column with scheme eligibility (bool), by default None.
        size_col : str, optional
            Name of the dataframe column with the number of households in consumer profile if being considered, by default 0.
        unit_converter : float, optional
            Value to divide electricity and gas consumption values from dataframe by to convert to MWh, by default 1.

        Returns
        -------
        Consumer
            Consumer instance.
        """

        def safe_get(col_name, default=None):
            """Helper function to retrieve column value if column name is provided."""
            return df.loc[row, col_name] if col_name else default

        name = safe_get(name_col)
        archetype = safe_get(archetype_col)
        net_annual_income = safe_get(net_annual_income_col)
        main_heating_fuel = safe_get(main_heating_fuel_col)
        gas_consumption = safe_get(gas_consumption_col, 0) / unit_converter
        electricity_consumption = (
            safe_get(electricity_consumption_col, 0) / unit_converter
        )
        net_income_decile = safe_get(net_income_decile_col, None)
        unmetered_fuel_spend = safe_get(unmetered_fuel_spend_col, 0)
        scheme_eligible = safe_get(scheme_eligible_col, False)
        size = safe_get(size_col, 0)

        return cls(
            name=name,
            archetype=archetype,
            net_annual_income=net_annual_income,
            net_income_decile=net_income_decile,
            main_heating_fuel=main_heating_fuel,
            gas_consumption=gas_consumption,
            electricity_consumption=electricity_consumption,
            unmetered_fuel_spend=unmetered_fuel_spend,
            scheme_eligible=scheme_eligible,
            size=size,
            gas_tariff=gas_tariff,
            electricity_tariff=electricity_tariff,
        )

    def __repr__(self):
        """Printable representation of Consumer instance."""
        attributes = [
            (key, value)
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        ]
        properties = [
            (key, getattr(self, key))
            for key, value in self.__class__.__dict__.items()
            if isinstance(value, property)
        ]
        all_items = attributes + properties
        repr_string = f"{self.__class__.__name__}("
        repr_string += ", ".join([f"{key}={repr(value)}" for key, value in all_items])
        repr_string += ")"
        return repr_string

    def boiler_to_hp_savings(
        self,
        boiler_efficiency: float = 0.85,
        hp_efficiency: float = 3.0,
        heating_pct: float = 0.97,
    ) -> float:
        """Returns estimated savings, in £, if household is assumed to switch from a gas boiler for heat to an electric heat pump.

        Parameters
        ----------
        boiler_efficiency : float, optional
            Assumed efficiency of gas boiler, by default 0.85
        hp_efficiency : float, optional
            Assumed efficiency of heat pump, by default 3.0
        heating_pct : float, optional
            Percentage of gas consumption that is assumed to be for heating, by default 0.97
        """
        boiler_demand = self.gas_consumption * heating_pct

        heat_demand = boiler_demand * boiler_efficiency

        hp_demand = heat_demand / hp_efficiency

        # Include gas standing charge in running costs
        boiler_running_cost = self.gas_tariff.calculate_total_consumption(boiler_demand)
        # Exclude electricity standing charge as assumed to already be paid regardless of heat pump
        hp_running_cost = self.electricity_tariff.calculate_variable_consumption(
            hp_demand
        )

        return hp_running_cost - boiler_running_cost
