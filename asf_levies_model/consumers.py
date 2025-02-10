import pandas as pd
import copy
from typing import Optional, Dict, Union

from asf_levies_model.tariffs import Tariff


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
        combined_fuel_bill: Combined electricity and gas final bill, including VAT, after any social support adjustment, in £.

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
        gas_tariff: Tariff,
        electricity_tariff: Tariff,
        unmetered_fuel_spend: float = 0.0,
        scheme_eligible: bool = False,
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
        gas_tariff : Tariff
            Tariff object to be used to calculate the consumer's gas bill.
        electricity_tariff : Tariff
            Tariff object to be used to calculate the consumer's electricity bill.
        unmetered_fuel_spend : float, optional
            Annual amount spent on unmetered fuel (i.e., fuel that is not gas or electricity), in £, by default 0.
        scheme_eligible : bool, optional
            Eligibilty for social support scheme, by default False.
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

        self.electricity_tariff = electricity_tariff
        self.gas_tariff = gas_tariff

        self._electricity_bill = None
        self._gas_bill = None

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
    def combined_fuel_bill(self) -> float:
        """Get the combined final bill for electricity and gas (after any social support adjustment).

        Returns
        -------
        float
            Annual combined fuel bill, including VAT, in £.
        """
        return self.gas_bill + self.electricity_bill

    def apply_social_support_adjustment(
        self,
        adjustment_fuel: str,
        adjustment_parameter: Union[float, Dict],
        adjustment_mode: str,
        inplace: bool = False,
    ) -> "Consumer | None":
        """Overwrites the electricity or gas bill property with an updated value reflected a social support adjustment (discount or additional cost).

        Parameters
        ----------
        adjustment_fuel : str
            Fuel bill to be adjusted, accepted strings are "electricity" and "gas".
        adjustment_parameter : Union[float, Dict]
            Value with which to adjust the fuel bill depending on adjustment mode. If adjustment mode is:
            (a) flat adjustment: Value (£) to be added to the total bill.
            (b) percentage discount: Percentage (%) of subtotal bill to be subtracted.
            (c) unit discount: Value (£/MWh) to be multiplied by fuel consumption, and product subtracted from the total bill.
            (d) rising block: Applies a varying unit discount for specified blocks of consumption units. Dictionary with keys "thresholds" and "discounts".
                Value of "thresholds" and "discounts" keys must be provided as List[float].
        adjustment_mode : str
            Acceptable strings are "flat adjustment", "percentage discount", "unit discount" and "rising block".
        inplace : bool
            Make fuel bill change in place (True) or return copy (False), by default False.

        Raises
        ------
        ValueError
            Error raised if an invalid adjustment mode is provided.
        ValueError
            Error raised if an invalid fuel type is provided.
        """
        # Work with a copy if not inplace
        obj = self if inplace else copy.deepcopy(self)

        # Check valid fuel type is given
        if adjustment_fuel not in ["electricity", "gas"]:
            raise ValueError(
                "Please specify the fuel bill to adjust (electricity or gas)."
            )

        # Define lookup dictionaries
        bill = {"electricity": self.electricity_bill, "gas": self.gas_bill}
        subtotal_bill = {
            "electricity": self.electricity_subtotal_bill,
            "gas": self.gas_subtotal_bill,
        }
        consumption = {
            "electricity": self.electricity_consumption,
            "gas": self.gas_consumption,
        }

        # Calculate adjusted total bills
        if adjustment_mode == "flat adjustment":
            adjusted_bill = bill[adjustment_fuel] + adjustment_parameter
        elif adjustment_mode == "percentage discount":
            adjusted_bill = bill[adjustment_fuel] - (
                (adjustment_parameter / 100) * subtotal_bill[adjustment_fuel]
            )
        elif adjustment_mode == "unit discount":
            adjusted_bill = bill[adjustment_fuel] - (
                consumption[adjustment_fuel] * adjustment_parameter
            )
        elif adjustment_mode == "rising block":

            thresholds = adjustment_parameter["thresholds"]
            discounts = adjustment_parameter["discounts"]

            discount_amounts = []
            for i in range(len(thresholds)):

                # First block
                if i == 0:
                    applicable_units = min(consumption[adjustment_fuel], thresholds[i])

                # Subsequent blocks
                else:
                    applicable_units = (
                        min(consumption[adjustment_fuel], thresholds[i])
                        - thresholds[i - 1]
                    )

                # Discount for applicable units in this block
                if applicable_units > 0:
                    discount_amounts.append(applicable_units * discounts[i])

                # Stop loop if consumption is below current threshold
                if consumption[adjustment_fuel] <= thresholds[i]:
                    break

            # Apply total discount to bill
            adjusted_bill = bill[adjustment_fuel] - sum(discount_amounts)

        else:
            raise ValueError(
                "Please provide an adjustment mode from the following: flat adjustment, percentage_discount, unit discount, rising block."
            )

        # Update attribute
        total_bill = {"electricity": "electricity_bill", "gas": "gas_bill"}
        setattr(obj, total_bill[adjustment_fuel], adjusted_bill)

        # Return updated Consumer object if not inplace
        return None if inplace else obj

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
            if key != "name" and not key.startswith("_") and key != "scheme_eligible"
        ]
        properties = [
            (key, getattr(self, key))
            for key, value in self.__class__.__dict__.items()
            if isinstance(value, property)
        ]
        attributes.extend(properties)
        df = pd.DataFrame(attributes, columns=["Attribute", "Value"])
        df["Name"] = self.name
        df["Eligible for support"] = self.scheme_eligible
        return df[["Name", "Eligible for support", "Attribute", "Value"]]

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
        gas_tariff: Tariff,
        electricity_tariff: Tariff,
        net_income_decile_col: Optional[str] = None,
        unmetered_fuel_spend_col: Optional[str] = None,
        unit_converter: float = 1.0,
        eligible: bool = False,
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
        gas_tariff : Tariff
            Gas tariff object for consumer bill to be calculated with.
        electricity_tariff : Tariff
            Electricity tariff object for consumer bill to be calculated with.
        net_income_decile_col : str, optional
            Name of the dataframe column with income decile (int), by default None.
        unmetered_fuel_spend_col : str, optional
            Name of the dataframe column with annual unmetered fuel spend amount (float), by default None.
        unit_converter : float, optional
            Value to divide electricity and gas consumption values from dataframe by to convert to MWh, by default 1.
        eligible : bool, by default False
            If True, Consumer is to have scheme_eligibility = True.

        Returns
        -------
        Consumer
            Consumer instance.
        """
        row_of_interest = df.iloc[row]

        name = row_of_interest.get(name_col)
        archetype = row_of_interest.get(archetype_col)
        net_annual_income = row_of_interest.get(net_annual_income_col)
        main_heating_fuel = row_of_interest.get(main_heating_fuel_col)
        gas_consumption = row_of_interest.get(gas_consumption_col, 0) / unit_converter
        electricity_consumption = (
            row_of_interest.get(electricity_consumption_col, 0) / unit_converter
        )
        net_income_decile = row_of_interest.get(net_income_decile_col, None)
        unmetered_fuel_spend = row_of_interest.get(unmetered_fuel_spend_col, 0)

        return cls(
            name=name,
            archetype=archetype,
            net_annual_income=net_annual_income,
            net_income_decile=net_income_decile,
            main_heating_fuel=main_heating_fuel,
            gas_consumption=gas_consumption,
            electricity_consumption=electricity_consumption,
            unmetered_fuel_spend=unmetered_fuel_spend,
            scheme_eligible=eligible,
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
        """Returns estimated savings, in £, if household is assumed to switch from a gas boiler \
for heating and hot water to an electric heat pump. Values are exclusive of VAT.

        Parameters
        ----------
        boiler_efficiency : float, optional
            Assumed efficiency of gas boiler, by default 0.85
        hp_efficiency : float, optional
            Assumed efficiency of heat pump, by default 3.0
        heating_pct : float, optional
            Percentage of gas consumption that is assumed to be for heating and hot water, by default 0.97
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


class ConsumerCollection:
    """A container for Consumer objects."""

    def __init__(
        self, name: str, consumers: list, group_sizes: Optional[Dict] = None
    ) -> None:
        """Initializes a ConsumerCollection instance based on a list of provided Consumer objects.

        Parameters
        ----------
        name : str
            Name for ConsumerCollection instance
        consumers : list
            List of Consumer objects
        group_sizes : Optional[Dict], optional
            Dictionary acting as a look-up for number of households represented by each consumer object in collection, by default None
        """

        self.name = name
        self.consumers = consumers

        if not group_sizes:
            group_sizes = {consumer.name: 1 for consumer in self.consumers}
        self.group_sizes = group_sizes

    @classmethod
    def from_dataframe(
        cls,
        collection_name: str,
        df: pd.DataFrame,
        rows: range,
        name_col: str,
        archetype_col: str,
        net_annual_income_col: str,
        main_heating_fuel_col: str,
        gas_consumption_col: str,
        electricity_consumption_col: str,
        gas_tariff: Tariff,
        electricity_tariff: Tariff,
        net_income_decile_col: Optional[str] = None,
        unmetered_fuel_spend_col: Optional[str] = None,
        unit_converter: float = 1.0,
        model_eligibility_sets: bool = True,
    ) -> "ConsumerCollection":
        """_summary_

        Parameters
        ----------
        collection_name : str
            Name of ConsumerCollection to be instantiated.
        df : pd.DataFrame
            Dataframe where each row corresponds to a consumer profile and columns describe (at least) name, net annual, income, main heating fuel, annual gas consumption, annual electricity consumption.
        rows : range
            Row indices in dataframe for consumer profile to instantiate.
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
        gas_tariff : Tariff
            Gas tariff object for consumer bill to be calculated with.
        electricity_tariff : Tariff
            Electricity tariff object for consumer bill to be calculated with.
        net_income_decile_col : Optional[str], optional
            Name of the dataframe column with income decile (int), by default None.
        unmetered_fuel_spend_col : Optional[str], optional
            Name of the dataframe column with annual unmetered fuel spend amount (float), by default None.
        unit_converter : float, optional
            Value to divide electricity and gas consumption values from dataframe by to convert to MWh, by default 1.0.
        model_eligibility_sets : bool, optional
            If True, ConsumerCollection will be populated with two sets of identical Consumer objects but one set with scheme_eligibility=True and one set scheme_eligibility=False, by default True

        Returns
        -------
        ConsumerCollection
            ConsumerCollection instance.
        """

        if model_eligibility_sets == False:
            consumers = [
                Consumer.consumer_from_dataframe(
                    df=df,
                    row=row,
                    name_col=name_col,
                    archetype_col=archetype_col,
                    net_annual_income_col=net_annual_income_col,
                    net_income_decile_col=net_income_decile_col,
                    main_heating_fuel_col=main_heating_fuel_col,
                    gas_consumption_col=gas_consumption_col,
                    electricity_consumption_col=electricity_consumption_col,
                    unmetered_fuel_spend_col=unmetered_fuel_spend_col,
                    gas_tariff=gas_tariff,
                    electricity_tariff=electricity_tariff,
                    unit_converter=unit_converter,
                    eligible=False,
                )
                for row in rows
            ]
        else:
            eligible_consumers = [
                Consumer.consumer_from_dataframe(
                    df=df,
                    row=row,
                    name_col=name_col,
                    archetype_col=archetype_col,
                    net_annual_income_col=net_annual_income_col,
                    net_income_decile_col=net_income_decile_col,
                    main_heating_fuel_col=main_heating_fuel_col,
                    gas_consumption_col=gas_consumption_col,
                    electricity_consumption_col=electricity_consumption_col,
                    unmetered_fuel_spend_col=unmetered_fuel_spend_col,
                    gas_tariff=gas_tariff,
                    electricity_tariff=electricity_tariff,
                    unit_converter=unit_converter,
                    eligible=True,
                )
                for row in rows
            ]
            ineligible_consumers = [
                Consumer.consumer_from_dataframe(
                    df=df,
                    row=row,
                    name_col=name_col,
                    archetype_col=archetype_col,
                    net_annual_income_col=net_annual_income_col,
                    net_income_decile_col=net_income_decile_col,
                    main_heating_fuel_col=main_heating_fuel_col,
                    gas_consumption_col=gas_consumption_col,
                    electricity_consumption_col=electricity_consumption_col,
                    unmetered_fuel_spend_col=unmetered_fuel_spend_col,
                    gas_tariff=gas_tariff,
                    electricity_tariff=electricity_tariff,
                    unit_converter=unit_converter,
                    eligible=False,
                )
                for row in rows
            ]
            consumers = eligible_consumers + ineligible_consumers

        return cls(name=collection_name, consumers=consumers)

    def deepcopy(self) -> "ConsumerCollection":
        """Returns deep copy of ConsumerCollection instance."""
        return copy.deepcopy(self)

    def apply_support_to_eligible_consumers(
        self,
        adjustment_fuel: str,
        adjustment_parameter: Union[float, Dict],
        adjustment_mode: str,
        inplace: bool = False,
    ) -> Optional["ConsumerCollection"]:
        """Applies social support adjustment to the fuel bills of eligible Consumers in ConsumerCollection. If inplace=False (default), returns a new instance of ConsumerCollection with applied support."""
        consumers_with_support = []
        for consumer in self.consumers:
            if consumer.scheme_eligible == True:
                consumers_with_support.append(
                    consumer.apply_social_support_adjustment(
                        adjustment_fuel=adjustment_fuel,
                        adjustment_parameter=adjustment_parameter,
                        adjustment_mode=adjustment_mode,
                        inplace=False,
                    )
                )
            else:
                consumers_with_support.append(consumer)

        if inplace:
            self.consumers = consumers_with_support
            return None
        else:
            return ConsumerCollection(
                name=self.name + " with applied support",
                consumers=consumers_with_support,
            )

    def tidy_summary_consumers(self, scenario_name: Optional[str]) -> pd.DataFrame:
        """Returns a Pandas DataFrame in tidy format listing all attributes of each Consumer object in ConsumerCollection.

        Parameters
        ----------
        scenario_name : Optional[str]
            Name of scenario run, if applicable, to be added as an additional column in the DataFrame.
        """
        tidy_summary = pd.concat(
            [consumer.get_tidy_summary() for consumer in self.consumers]
        )
        if scenario_name:
            tidy_summary["Scenario"] = scenario_name
        return tidy_summary
