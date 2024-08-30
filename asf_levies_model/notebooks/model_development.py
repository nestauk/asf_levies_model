# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     comment_magics: true
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# Let's start by prototyping a class to represent a levy.
#
# This Levy class could be a base class for specific Levy classes to inherit from as we develop our understanding of levies, but for now let's assume a generic levy.
#
# Actually, we likely only need a generic levy until we come to forecasting values as each levy will then have it's own calculation.


# %%
class Levy:
    def __init__(self, name, basis, fuel, cost):
        self.name = name
        self.basis = basis
        self.fuel = fuel
        self.cost = cost

    @property
    def basis(self):
        return self._basis

    @basis.setter
    def basis(self, value):
        if not value in ["variable", "fixed", "taxation"]:
            raise ValueError(
                "basis expected to be one of: ['variable', 'fixed', 'taxation']"
            )
        self._basis = value

    @property
    def fuel(self):
        return self._fuel

    @fuel.setter
    def fuel(self, value):
        if not value in ["gas", "electricity"]:
            raise ValueError("fuel expected to be one of: ['gas', 'electricity']")
        self._fuel = value

    def calculate_variable_cost(self, consumption):
        if self.basis != "variable":
            raise ValueError(
                f"Cannot calculate variable cost as cost basis is {self.basis}"
            )
        return self.cost * consumption

    def calculate_fixed_cost(self):
        if self.basis != "fixed":
            raise ValueError(f"Cannot return fixed cost as cost basis is {self.basis}")
        return self.cost

    def calculate_revenue(self, value):
        if self.basis != "taxation":
            raise ValueError(
                f"Cannot return cost to general taxation as cost basis is {self.basis}"
            )
        return self.cost * value

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        cost_basis = {"variable": "£/MWh", "fixed": "£/customer", "taxation": ""}
        return f'{type(self).__name__}(name="{self.name}", basis="{self.basis}", fuel="{self.fuel}", cost={self.cost} {cost_basis[self.basis]})'


# %%
# Define some levies
# electricity
whd_electricity = Levy(
    "Warm Homes Discount Electricity", "fixed", "electricity", 10.909265371253545
)
aahedc = Levy(
    "Assistance for Areas with High Electricity Distribution Costs",
    "variable",
    "electricity",
    0.4551192437813739,
)
eco_electricity = Levy(
    "ECO and GBIS Electricity", "variable", "electricity", 8.699329123454325
)
ro = Levy("Renewables Obligation", "variable", "electricity", 31.78243)
fit = Levy("Feed-in-tariff", "variable", "electricity", 7.63909170564922)

# gas
whd_gas = Levy("Warm Homes Discount Gas", "fixed", "gas", 10.909265371253545)
ggl = Levy("Green Gas Levy", "fixed", "gas", 0.38325)
eco_gas = Levy("ECO and GBIS Gas", "variable", "gas", 2.99410745173736)

# %% [markdown]
# How should levy switching be managed?
#
# Should we load existing levies to initialise a levy and then activate a switch in basis or fuel? That way we don't precompute expacted values for all options unless we need to. Should presumably be quite low costs to do.

# %%
# Consumption
TYPICAL_CONSUMPTION_ELECTRICITY = 2.7
TYPICAL_CONSUMPTION_GAS = 11.5


# %%
def calculate_policy_costs(
    levies: list[Levy],
    electricity_consumption: float = TYPICAL_CONSUMPTION_ELECTRICITY,
    gas_consumption: float = TYPICAL_CONSUMPTION_GAS,
) -> float:
    """Calculate policy costs for a given collection of levies."""
    policy_cost = {
        "gas": 0,
        "electricity": 0,
        "gas_nil": 0,
        "electricity_nil": 0,
        "gas_variable": 0,
        "electricity_variable": 0,
        "gas_variable_unit": 0,
        "electricity_variable_unit": 0,
    }
    consumption = {"electricity": electricity_consumption, "gas": gas_consumption}
    for levy in levies:
        if levy.basis == "fixed":
            policy_cost[levy.fuel] += levy.calculate_fixed_cost()
            policy_cost[f"{levy.fuel}_nil"] += levy.calculate_fixed_cost()
        elif levy.basis == "variable":
            policy_cost[levy.fuel] += levy.calculate_variable_cost(
                consumption[levy.fuel]
            )
            policy_cost[f"{levy.fuel}_variable"] += levy.calculate_variable_cost(
                consumption[levy.fuel]
            )
            policy_cost[f"{levy.fuel}_variable_unit"] += levy.cost
    return policy_cost


# %%
policy_costs = calculate_policy_costs(
    [whd_electricity, aahedc, eco_electricity, ro, fit, whd_gas, ggl, eco_gas]
)
policy_costs


# %%
class Tariff:
    def __init__(
        self,
        name,
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
        self.fuel = fuel
        self.df_nil = df_nil  # Direct Fuel Cost
        self.cm_nil = cm_nil  # Capacity Market Cost
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
                if component is not None
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
                if component is not None
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


# %%
electricity = Tariff(
    name="Electricity Standard Credit",
    fuel="electricity",
    df_nil=None,
    cm_nil=None,
    aa_nil=0.00,
    pc_nil=policy_costs["electricity_nil"],
    nc_nil=120.59,
    oc_nil=50.65,
    smncc_nil=11.08,
    paac_nil=17.55,
    pap_nil=11.27,
    ebit_nil=5.56,
    hap_nil=1.57,
    levelisation_nil=None,
    df=96.763,
    cm=6.97,
    aa=5.130,
    pc=policy_costs["electricity_variable_unit"],
    nc=29.04444444,
    oc=15.9,
    smncc=1.607407,
    paac=0,
    pap=11.9,
    ebit=5.41111,
    hap=2.8148148,
    levelisation=None,
)

# %%
electricity.calculate_nil_consumption()

# %%
electricity.calculate_variable_consumption(TYPICAL_CONSUMPTION_ELECTRICITY)

# %%
electricity.calculate_total_consumption(TYPICAL_CONSUMPTION_ELECTRICITY)

# %%
electricity.calculate_total_consumption(TYPICAL_CONSUMPTION_ELECTRICITY, vat=True)


# %%


# %%
class Levy:
    def __init__(
        self,
        name,
        electricity,
        gas,
        general_taxation,
        electricity_variable_rate,
        electricity_fixed_rate,
        gas_variable_rate,
        gas_fixed_rate,
        revenue,
    ):
        self.name = name

        # Mode split
        self.electricity = electricity
        self.gas = gas
        self.general_taxation = general_taxation

        # Mode of levying
        self.electricity_variable_rate = electricity_variable_rate
        self.electricity_fixed_rate = electricity_fixed_rate
        self.gas_variable_rate = gas_variable_rate
        self.gas_fixed_rate = gas_fixed_rate

        # Total revenue
        self.revenue = revenue


# %%
# RO

ro = Levy(
    name="Renewable Obligation",
    electricity=1.0,
    gas=0.0,
    general_taxation=0.0,
    electricity_variable_rate=31.78243,
    electricity_fixed_rate=None,
    gas_variable_rate=None,
    gas_fixed_rate=None,
    revenue=7_890_000_000,
)

# %% [markdown]
# My read is that all electricity suppliers are required to participate in RO, regardless of size, if they have a supply of > 0.
#
# Therefore, under a hypothetical supply scenario, all gas suppliers should also be obligateed.
#
# By comparison, ECO is an obligation on medium and large suppliers. A supplier meets the obligation threshold according to customer numbers and supply volumes.

# %%
# From annex 4 eco sheet
eco_elec_volume = 93_503_455
eco_gas_supply_volume = 271_672_723

# %%
# Total supply volumes Dukes
dukes_net_electricity = 245_541_160
dukes_net_gas = 237_099_850

# %%
res_elec_demand = 8603.78787390749 * 11.63
res_gas_demand = 21763.9242306998 * 11.63

# %%
res_elec_demand, res_gas_demand

# %%
res_elec_demand / (res_elec_demand + res_gas_demand)

# %%
res_elec_demand / res_gas_demand

# %%
eco_elec_volume / eco_gas_supply_volume

# %%
# Subnational consumption of gas (non-weather corrected)
gb_domestic_2022 = 265_197_947
gb_total_2022 = 435_369_123

# %%
# Subnational consumption of electricity (gb)
