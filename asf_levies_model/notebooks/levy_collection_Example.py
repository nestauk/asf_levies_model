# %%
from asf_levies_model.levies import RO, AAHEDC, GGL, ECO, WHD, FIT, LevyCollection
from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment
from asf_levies_model.summary import create_scenario_weights_dict, _rebalance_levies

from asf_levies_model.getters import load_data as data

# %%
# Denominator values from Desnz subnational consumption domestic data
supply_elec = 94_200_366
supply_gas = 265_197_947
customers_gas = 24_503_683
customers_elec = 29_078_770

denominator_values = {
    "supply_elec": supply_elec,
    "supply_gas": supply_gas,
    "customers_gas": customers_gas,
    "customers_elec": customers_elec,
}
denominators = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}

# DESNZ GB total electricity consumption - all meters (2022)
total_supply_elec = 250_020_739
exempt_eii_supply = 9_417_916  # Oct-Dec 2024 period, Annex 4, New FIT methodology tab
fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

# %% [markdown]
# ### LevyCollection
#
# The LevyCollection is a container for levies and some associated information (notably denominators). It aims to make working with levies and especially rebalancing easier.
#
# In the creation below note that I'm passing the `denominator_values` object, not the `denominators`. If the denominators for each levy should all be the same it is sufficient to just pass a dictionary of the consumption and customer numbers as per `denominator_values`, if you want to set sepcific denominators on a levy-by-levy basis you can do this by passing the `denominators` object.

# %%
fileobj = data.download_annex_4(as_fileobject=True)

ro = RO.from_dataframe(data.process_data_RO(fileobj), denominator=supply_elec)
aahedc = AAHEDC.from_dataframe(
    data.process_data_AAHEDC(fileobj), denominator=supply_elec
)
ggl = GGL.from_dataframe(data.process_data_GGL(fileobj), denominator=customers_gas)
eco = ECO.from_dataframe(data.process_data_ECO(fileobj))
whd = WHD.from_dataframe(
    data.process_data_WHD(fileobj),
    customers_gas=customers_gas,
    customers_elec=customers_elec,
)
fit = FIT.from_dataframe(
    data.process_data_FIT(fileobj), scaling_factor=fit_scaling_factor
)

pc = LevyCollection(
    "Policy Costs", "pc", [ro, aahedc, ggl, eco, whd, fit], denominator_values
)

# %% [markdown]
# ### Summarise Levies
#
# Output a pandas DataFrame of the key levy statistics from a LevyCollection.

# %%
pc.summarise_levies()

# %% [markdown]
# ## Rebalance levies to reflect denominators
# For internal consistency, it can be useful to rebalance levies against the specific denominators you are using. This is because some levies use the revenue provided by ofgem, but the rate may have been calculated using a slightly different denominator. As such, rebalancing will include the difference in denominators as a component of the difference in cost. This is mitigated by rebalancing to the analysis denominators, but means that the base case will be slightly different to that published by ofgem.

# %%
pc_denom_rebal = pc.rebalance_to_denominators()

# %%
pc.calculate_levies(2.7, 11.5, True, True)

# %%
# Slight difference in policy costs after denominator rebalancing.
pc_denom_rebal.calculate_levies(2.7, 11.5, True, True)

# %% [markdown]
# ### Compute a range of costs using LevyCollection

# %%
# Old way
sum(
    [
        levy.calculate_levy(2.7, 11.5, True, True)
        for levy in [ro, aahedc, ggl, eco, whd, fit]
    ]
)

# %%
# With Levy Collection
pc.calculate_levies(2.7, 11.5, True, True)

# %%
# Old way
sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in [ro, fit]])

# %%
# With Levy Collection
pc.calculate_levies(2.7, 11.5, True, True, by=["ro", "fit"])

# %% [markdown]
# The same is true for calculating the fixed and variable components of policy costs.

# %%
# old way
sum(
    [
        levy.calculate_variable_levy(2.7, 11.5)
        for levy in [ro, aahedc, ggl, eco, whd, fit]
    ]
)

# %%
pc.calculate_variable_levies(2.7, 11.5)

# %%
# old way
sum(
    [levy.calculate_fixed_levy(True, True) for levy in [ro, aahedc, ggl, eco, whd, fit]]
)

# %%
pc.calculate_fixed_levies(True, True)

# %% [markdown]
# ### Levy Rebalancing with LevyCollection
#
# Demonstrating rebalancing with a scenario that rebalances RO and FiT from electricity to gas.
#
# Note that the `LevyCollection.rebalance_levies()` method works with either a single set of rebalancing weights, in which case the provided `scenario_name` is used to identify the rebalanced levies, or if a dictionary of rebalancing weights indexed by scenarios is passed, the `scenario_name` must be a key in the rebalancing weights dictionary.

# %%
# Generate a scenario template based on the levies in the LevyCollection
rebalance_ro_fit_weights = create_scenario_weights_dict(pc)

# %%
# update the specific levies you want to rebalance.
for levy in pc[["ro", "fit"]]:
    rebalance_ro_fit_weights[levy.short_name] = {
        "new_electricity_weight": 0,
        "new_gas_weight": 1,
        "new_tax_weight": 0,
        "new_variable_weight_elec": 0,
        "new_fixed_weight_elec": 0,
        "new_variable_weight_gas": levy.electricity_variable_weight,
        "new_fixed_weight_gas": levy.electricity_fixed_weight,
    }

# %%
# old approach to rebalancing
rebalanced_levies = _rebalance_levies(
    [ro, aahedc, ggl, eco, whd, fit],
    {"rebalance_ro_and_fit_to_gas": rebalance_ro_fit_weights},
    denominators,
    "rebalance_ro_and_fit_to_gas",
)
# Get typical total for rebalanced levies
sum([levy.calculate_levy(2.7, 11.5, False, False) for levy in rebalanced_levies])

# %%
rebalanced_pc = pc.rebalance_levies(
    rebalance_ro_fit_weights, "rebalance_ro_and_fit_to_gas"
)
rebalanced_pc.calculate_levies(2.7, 11.5, False, False)

# %% [markdown]
# #### Updating revenues values in a LevyCollection
#
# We may wish to resize a levy to deliver more (or less) revenue against consumption or customers.
#
# The `LevyCollection.update_revenues()` method takes a dictionary of levy short names paired with revenue adjustments as below.
#
# Using the `update_revenues()` method, rather than simply setting the revenue attribute ensures that the levy rates reflect the updated revenues.

# %%
pc["whd"].revenue

# %%
pc.update_revenues(new_revenues={"whd": pc["whd"].revenue * 2}, inplace=True)

# %%
pc["whd"].revenue

# %% [markdown]
# #### Other convenient LevyCollection methods
#
# The `LevyCollection` implements a `union_levies()` method to collapse all levies into a single levy for some analytical purposes.
#
# In addition, LevyCollections can be indexed by the levy short name, iterated over and have specific levies deleted.
#
# Ideally, to add a new levy you will create a new LevyCollection.

# %%
# union levies example
union = pc.union_levies()
union

# %%
# iterate over levies easily
[levy.name for levy in pc]

# %%
# index based on levy short name
# returns either single levy or list of levies.
pc["ro"]

# %%
# Index several levies
pc[["ro", "whd"]]

# %%
# delete a levy from the Levy collection
del pc["whd"]
pc.levy_short_names

# %% [markdown]
# ### Connecting LevyCollection to Tariffs
#
# The `Tariff` object has been updated to make changing policy costs as a reuslt of rebalancing easier. Now you can simply pass a `LevyCollection` to the `Tariff.update_policy_costs()` method.

# %%
# Load tariff (Other Payment method) data from Annex 9
fileobject = data.download_annex_9(as_fileobject=True)
elec_other_payment_nil = data.process_tariff_elec_other_payment_nil(fileobject)
elec_other_payment_typical = data.process_tariff_elec_other_payment_typical(fileobject)
gas_other_payment_nil = data.process_tariff_gas_other_payment_nil(fileobject)
gas_other_payment_typical = data.process_tariff_gas_other_payment_typical(fileobject)
fileobject.close()

# %%
# Create tariff objects
baseline_elec_tariff = ElectricityOtherPayment.from_dataframe(
    elec_other_payment_nil, elec_other_payment_typical
)

baseline_gas_tariff = GasOtherPayment.from_dataframe(
    gas_other_payment_nil, gas_other_payment_typical
)

# %%
# baseline tariff cost
baseline_elec_tariff.calculate_total_consumption(2.7)

# %%
# Update policy costs
rebalanced_elec_tariff = baseline_elec_tariff.update_policy_costs(rebalanced_pc)

# %%
# New tariff cost.
rebalanced_elec_tariff.calculate_total_consumption(2.7)

# %%
# baseline tariff cost
baseline_gas_tariff.calculate_total_consumption(11.5)

# %%
rebalanced_gas_tariff = baseline_gas_tariff.update_policy_costs(rebalanced_pc)

# %%
rebalanced_gas_tariff.calculate_total_consumption(11.5)
