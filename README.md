# Energy Bills and Levies Model

## Description

Model of domestic energy bills and levies to test the impacts of changing different components of domestic energy bills, project these changes into the future, and investigate how impacts of changes vary across different household archetypes via distributional analysis.

## Setup for Development

If you want to develop code in this repo, enhancing what we already have or adding your own components, you should clone the existing repo dev branch.

First, if you're using linux or mac os it'll be useful for you to install [`direnv`](https://direnv.net/).

Secondly, we've used [`conda`](https://docs.anaconda.com/miniconda/).

If you're also on a unix-like os and you are using conda, run `make install` to configure the development environment:

- Setup the conda environment
- Configure `pre-commit`

If you're on Windows or you're using a different environment and dependency manager you'll have to figure it out. This will likely involve cloning the repo, creating an environment and installing the core dependencies.

## Setup for Use

If you just want to use the package as is, you can install from github using a command like:

`pip install git+https://github.com/nestauk/asf_levies_model.git`

## The config file

If you cloned the repo for development, you should find there is a config file at: ./asf_levies_model/config/base.yaml.

If you installed `asf_levies_model`, the config file will be wherever the package was installed on your computer, most likely the python 'site-packages' directory for the environment you're working in. To find where this is, you can run `python -m site` in the command line, this will print `sys.path` locations which should include `site-packages`. Should you need to change the `base.yaml` config file you can access it there.

To see the contents of the config file `base.yaml`, you can either open the base.yaml file or in python run:

```{python}
from asf_levies_model import config
print(config)
```

At present there are 2 sets of entries.

**data_sources** tells `asf_levies_model` where to find the ofgem data for `ofgem_annex_4` and `ofgem_annex_9`.
**data_downloads** tells `asf_levies_model` where to store downloaded annex data as well as where to find archetypes data if required.

You can change these to use different versions of the ofgem annex data (e.g. new versions that become available) or to change where the downloaded data are stored on your computer.

### Ofgem annex data

The ofgem annex data are the underlying data used to calculate the energy price cap for a given price cap period. Currently we are using two parts of this data:

- **Annex 4** - this is the policy costs annex, it contains all the data we're using to initialise the different levies on an energy bill.
- **Annex 9** - this is the tariff costs annex, it contains the overall values for different components of an energy bill. We use this data to initialise an energy bill.

There are other annexes that we're currently not using that cover other components of the bill like direct fuel costs or network costs.

In general, the config links to the relevant document given on ofgem's [Energy price cap (default tariff) levels](https://www.ofgem.gov.uk/energy-policy-and-regulation/policy-and-regulatory-programmes/energy-price-cap-default-tariff-policy/energy-price-cap-default-tariff-levels) page under 'Other documents' for the relevant price cap period.

Note that we have tested our code on several price cap periods, however there is a risk that ofgem change the formatting of the annexes and break our code.

## Introduction to the levies model

At present the levies model defines two generic objects, a `Levy()` and a `Tariff()`. You can import these into a script like this:

```{python}
from asf_levies_model.levies import Levy
from asf_levies_model.tariffs import Tariff
```

## The Levy object

The generic `Levy()` class defines the basic requirements for creating a levy and the methods needed to calculate the total, variable and fixed costs, to update or change the revenue, and to rebalance the levy.

Let's create a basic levy:

```{python}
generic_levy = Levy(
    name='my generic levy',
    short_name='mgl',
    electricity_weight=1,
    gas_weight=0,
    tax_weight=0,
    electricity_variable_weight=1,
    electricity_fixed_weight=0,
    gas_variable_weight=0,
    gas_fixed_weight=0,
    electricity_variable_rate=100_000_000/94_200_365,
    electricity_fixed_rate=0,
    gas_variable_rate=0,
    gas_fixed_rate=0,
    general_taxation=0,
    revenue=100_000_000,
)
```

In this example we've set up a levy that aims to raise £100m for some purpose (the revenue), it's a levy totally on electricity, and is levied entirely against electricity units. The variable rate is provided as the revenue divided by annual consumption in MWh, in this case a total equivalent to domestic electricity consumption. Calling `repr()` on `generic_levy` will give a summary of the levy.

### Calculating the cost of a levy

The `generic_levy` object then enables some simple calculations to be made via the `.calculate_*` methods:

- `.calculate_fixed_levy()` - calculates the fixed charge components of a levy for `electricity_customer` and/or `gas_customer`.
- `.calculate_variable_levy()` - calculates the variable charge components of a levy for given consumptions in MWh for `electricity_consumption` and/or `gas_consumption`.
- `.calculate_levy()` - calculates the sum of the fixed and variable components for given `electricity_consumption`, `gas_consumption`, `electricity_customer` and `gas_customer`.

Note that depending on the levy, all arguments won't necessarily be relevant, but they will be used in the calculation, so it's good practice to fully fill the options as in these examples:

```{python}
# Calculate the levy cost for a 'typical' household at 2.7MWh of annual electricity consumption.
var_cost = generic_levy.calculate_variable_levy(electricity_consumption=2.7, gas_consumption=0.0)

# Calculate the total levy cost.
total_cost = generic_levy.calculate_levy(electricity_consumption=2.7, gas_consumption=0.0, electricity_customer=False, gas_customer=False)
```

In the `generic_levy` case, we've created a levy that is only on electricity and is charged according to consumption (variable), therefore we can set other options to 0.0 (gas consumption) or False (electricity and gas customers - for fixed cost calculations).

In practice, we can just pass the full set of information and get the same answer back for `generic_levy` as per:

```{python}
total_cost = generic_levy.calculate_levy(electricity_consumption=2.7, gas_consumption=11.5, electricity_customer=True, gas_customer=True)
```

### Changing the levy revenue

If you want to update or change the revenue associated with a levy, use the `.update_revenue()` method. This will update the levy revenue and recalculate the levy rates either `inplace` or as a copy (the default), based on the existing levy set up for gas and/or electricity and variable and/or fixed rates.

The method implements two approaches, an `overwrite` approach as default, and an update approach. Overwriting sets a new revenue, while updating adds or subtracts a given amount from the existing revenue. The `supply_gas`, `supply_elec`, `customers_gas`, and `customers_elec` are the relevant consumption and customer numbers used to recalculate the levy rates. In the example below domestic estimates are used.

```{python}
# overwrite the levy revenue with a new value of £200m
generic_levy = generic_levy.update_revenue(new_revenue=200_000_000,
                                           supply_gas=265_197_947,
                                           supply_elec=94_200_366,
                                           customers_gas=24_503_683,
                                           customers_elec=29_078_770,
                                           overwrite=True,
    )
```

In some situations, you may want to add or remove a fixed amount to the existing revenue, as in the example below:

```{python}
# Update the levy revenue to be £10m larger
generic_levy = generic_levy.update_revenue(new_revenue=10_000_000,
                                           supply_gas=265_197_947,
                                           supply_elec=94_200_366,
                                           customers_gas=24_503_683,
                                           customers_elec=29_078_770,
                                           overwrite=False,
    )
```

Here, £10m is added to the existing revenue figure, if `new_revenue` had been specified as `-10_000_000` then £10m would have been removed.

### Rebalancing the levy

A major aim of this package is to explore levy rebalancing. This is achieved with the `.rebalance_levy()` method. This will create a new levy rate according to the rebalancing parameters specified for the levy revenue. There are 7 rebalancing parameter:

- **new_electricity_weight**: the proportion of the levy revenue to be applied to electricity connections and/or consumption.
- **new_gas_weight**: the proportion of the levy revenue to be applied to gas connections and/or consumption.
- **new_tax_weight**: the proportion of the levy revenue to be applid to general taxation (effectively removed from bills).

  _Note that `new_electricity_weight`, `new_gas_weight` and `new_tax_weight` should sum to 1._

- **new_variable_weight_elec**: the proportion of the electricity revenue to be allocated as a unit cost.
- **new_fixed_weight_elec**: the proportion of the electricity revenue to be allocated as a fixed cost.

  _Note that `new_variable_weight_elec`, `new_fixed_weight_elec` should either sum to 1, or both be set to 0._

- **new_variable_weight_gas**: the proportion of the gas revenue to be allocated as a unit cost.
- **new_fixed_weight_gas**: the proportion of the gas revenue to be allocated as a fixed cost.

  _Note that `new_variable_weight_gas`, `new_fixed_weight_gas` should either sum to 1, or both be set to 0._

In addition, there are 4 arguments used for the levy rate creation, as in the `.update_revenue()` method:

- **supply_gas**: the gas consumption denominator for calculating variable rates for gas.
- **supply_elec**: the electricity consumption denominator for calculating variable rates for electricity.
- **customers_gas**: the number of gas customers/meters denominator for calculating fixed rates for gas.
- **customers_elec**: the number of electricity customers/meters denominator for calculating fixed rates for electricity.

The default for `.rebalance_levy()` is to return a copy of the original levy subject to the rebalancing, however it can also be rebalanced `inplace` if required.

Rebalancing involves a number of parameters, let's have a look at it in practice, rebalancing our `generic_levy` from electricity to gas, sticking with a variable levy rate.

```{python}
# Define the denominators as a dictionary for convenience.
denominators = {'supply_elec':94_200_366,
                'supply_gas':265_197_947,
                'customers_gas':24_503_683,
                'customers_elec':29_078_770
                }

# Define the rebalancing parameters
rebalance = {'new_electricity_weight': 0,
             'new_gas_weight': 1,
             'new_tax_weight': 0,
             'new_variable_weight_elec': 0,
             'new_fixed_weight_elec': 0,
             'new_variable_weight_gas': 1,
             'new_fixed_weight_gas': 0,
             }

# Create the rebalanced levy
rebalanced_levy = generic_levy.rebalance_levy(**rebalance, **denominators)
```

The `rebalanced_levy` object should now report that it is a levy on gas with a given levy rate.

### Working with specific levies

The levies module also includes classes for 6 current levies defined as policy costs by Ofgem they can be imported like this:

```{python}
from asf_levies_model.levies import RO, AAHEDC, GGL, WHD, ECO, FIT
```

These levies are:

- RO - Renewables Obligation
- AAHEDC - Assistance for Areas with High Electricity Distribution Costs
- GGL - Green Gas Levy
- WHD - Warm Homes Discount
- ECO - Energy Company Obligation
- FIT - Feed-in Tariff

These levies are subclasses of the `Levy()` object, with some specific attributes and methods relevant to the levy in question. You could use them in the way we used `generic_levy` above, but the key addition to these specific levies is the class constructor `.from_dataframe()`. This allows you to instantiate the specific levy by passing a dataframe of relevant information from Ofgem's Annex 4 energy price cap spreadsheet. The `getters` module has some specific functions to access the relevant ofgem data.

### Getting Ofgem levies data

As previously discussed, the `config` file records a url corresponding to a version of the ofgem annex 4 spreadsheet (you can update this as new energy cap data is released). Relevant functions for getting this data are:

```{python}
from asf_levies_model.getters.load_data import (
    download_annex_4,
    process_data_RO,
    process_data_AAHEDC,
    process_data_GGL,
    process_data_WHD,
    process_data_ECO,
    process_data_FIT,
)
```

If you want to download the actual annex 4 spreadsheet, use `download_annex_4()` this will save the spreadsheet at the location specified in `config`, provided that location already exists, at present if that directory doesn't exist the function won't create it for you, it will error.

Once you've downloaded the annex 4 spreadsheet, the `process_data_*` functions will then attempt to use that downloaded file unless you choose to use a temporary fileobject.

The general approach looks like this:

```{python}
ro = RO.from_dataframe(process_data_RO(), denominator=94_200_366)
```

In this case, we provide a denominator for RO so that a revenue can be calculated, this is because RO doesn't strictly speaking have a revenue amount so we create one to facilitate rebalancing. Each specific levy is calculated differently, so the `.from_dataframe()` class methods have slightly different arguments depending on the levy:

- RO has `revenue` and `denominator` arguments, providing `revenue` simply sets the revenue amount, while providing `denominator` whch is assumed to be a measure of electricity supplied in MWh creates a revenue from the unit levy rate.
- AAHEDC has `revenue` and `denominator` arguments, for the same reason as RO.
- GGL has `revenue` and `denominator` arguments, for the same reason as RO.
- WHD has `revenue` to allow the revenue to be set, however by default it uses the 'TargetSpendingForSchemeYear' field in the Ofgem data. In addition, you can provide `customers_gas` and `customers_elec` (customer/meter counts) to calculate the electricity - gas balance for the levy as this is not given in the Ofgem data.
- ECO has `revenue` to allow the revenue to be set, however by default it uses the inflated costs for ECO4 and GBIS provided by Ofgem.
- FIT has `revenue` to allow the revenue to be set, however by default it uses the 'InflatedLevelisationFund' field in the Ofgem data. In addition, the `scaling_factor` argument allows the revenue to be scaled e.g. by the proportion of total electricity consumption that is domestic.

A full example of loading all 6 levies, for domestic denominators looks like:

```{python}
levies = [
    RO.from_dataframe(process_data_RO(), denominator=94_200_366),
    AAHEDC.from_dataframe(process_data_AAHEDC(), denominator=94_200_366),
    GGL.from_dataframe(process_data_GGL(), denominator=24_503_683),
    WHD.from_dataframe(process_data_WHD(), customers_gas=24_503_683, customers_elec=29_078_770),
    ECO.from_dataframe(process_data_ECO()),
    FIT.from_dataframe(process_data_FIT(scaling_factor=94_200_366/250_020_739))
    ]
```

The other approach to loading ofgem data is in-memory, removing the need to save the annex 4 spreadsheet on your computer:

```{python}
# create in-memory fileobject
fileobject_annex_4 = download_annex_4(as_fileobject=True)

# pass fileobject to process_data_* getter
ro = RO.from_dataframe(process_data_RO(fileobject_annex_4), denominator=94_200_366)

# close fileobject when done.
fileobject_annex_4.close()
```

The ofgem levies can be interrogated as `generic_levy` is above to calculate the levy amount.

### Rebalancing the Ofgem levies for analysis

If you want to explore existing levy rates and estimate costs for consumers with different electricity and gas consumption values, you can use the levies directly as created above.

However, if you want to rebalance and compare the levies, we recommend that you first rebalance the existing levies to a common set of denominators to make analysis internally consistent (at the expense of some external consistency). This is because each levy uses a slightly different denominator as required by relevant legislation and ofgem guidance, so rebalanced levies might not be entirely comparable to the status quo without using a common set of denominators. Here is an example of how to rebalance the levies initialised with Ofgem data.

```{python}
# Set denominator values as domestic values from subnational consumption accounts dataset (GB)
denominator_values = {
    "supply_elec": 94_200_366,
    "supply_gas": 265_197_947,
    "customers_gas": 24_503_683,
    "customers_elec": 29_078_770,
}
denominators = {
    key: denominator_values for key in ["ro", "aahedc", "ggl", "whd", "eco", "fit"]
}
# We need the existing levy values to rebalance (even though they don't change).
status_quo = {}
for levy in levies:
    status_quo[levy.short_name] = {
        "new_electricity_weight": levy.electricity_weight,
        "new_gas_weight": levy.gas_weight,
        "new_tax_weight": levy.tax_weight,
        "new_variable_weight_elec": levy.electricity_variable_weight,
        "new_fixed_weight_elec": levy.electricity_fixed_weight,
        "new_variable_weight_gas": levy.gas_variable_weight,
        "new_fixed_weight_gas": levy.gas_fixed_weight,
    }

# Total ofgem levy amount before rebalancing (for typical usage)
print(sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies]))

# Rebalance baseline levies
levies = [
    levy.rebalance_levy(
        **status_quo.get(levy.short_name), **denominators.get(levy.short_name)
    )
    for levy in levies
]

# Total levy amount after rebalancing (for typical usage)
print(sum([levy.calculate_levy(2.7, 11.5, True, True) for levy in levies]))
```

You should find that the difference in levy costs for a typical consumer is a handful of pence in the rebalanced levy.

### A Note on time series

Currently, the levy objects work with the latest energy price cap in the provided data only. The levy classes achieve this by taking the latest populated row of data. As such, if you wanted to explore earlier price cap periods it should simply be a case of getting the relevant dataframe from `process_data_*` and truncating the rows at the row relevant to the energy price cap period of interest.

## The Tariff object

The generic `Tariff()` class defines the basic requirements for creating a gas or electricity tariff and the methods needed to calculate the total, variable and fixed costs. The object reflects the components of an electricity bill listed in Ofgem's energy price cap annex 9.

Although you could manually construct a generic tariff in a similar way to what we've shown above for a generic levy, we're mostly interested in populating a tariff with the relevant Ofgem information and then manipulating the policy costs. This is what we'll demonstrate below.

### Getting Ofgem tariff data

As previously discussed, the `config` file records a url corresponding to a version of the ofgem annex 9 spreadsheet (you can update this as new energy cap data is released). Relevant functions for getting this data are:

```{python}
from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.getters.load_data import (
    download_annex_9,
    process_tariff_elec_other_payment_nil,
    process_tariff_elec_other_payment_typical,
    process_tariff_gas_other_payment_nil,
    process_tariff_gas_other_payment_typical
    )
```

If you want to download the actual annex 9 spreadsheet, use `download_annex_9()` this will save the spreadsheet at the location specified in `config`, provided that location already exists, at present if that directory doesn't exist the function won't create it for you, it will error.

Once you've downloaded the annex 9 spreadsheet, the `process_tariff_*` functions will then attempt to use that downloaded file unless you choose to use a temporary fileobject. Note that to populate a tariff object you need both the nil rate and typical rate dataframes, shown in the suffix of the getter functions.

In the example above, we're using the tariff classes for electricity and gas other payment methods, however we have also implemented the prepayment meter and standard credit tariffs and their relevant data getters as well. Note that we're using the GB averaged tariffs, currently we don't support geographical differentiation.

Create an electricity and gas tariff object like this:

```{python}
# Download annex 9 to the computer
# NB can also use a file object approach as shown for levies.
download_annex_9()

# Create an electricity tariff object
elec_other = ElectricityOtherPayment.from_dataframe(process_tariff_elec_other_payment_nil(),
                                                    process_tariff_elec_other_payment_typical())

gas_other = GasOtherPayment.from_dataframe(process_tariff_gas_other_payment_nil(),
                                           process_tariff_gas_other_payment_typical())
```

Note that the typical consumption data is provided by Ofgem for a typical electricity consumption of 2.7 MWh and a typical gas consumption of 11.5 MWh. We convert these to unit consumption in the object creation stage, the current typical consumption values are defaults, but should that change the `.from_dataframe()` constructor method accepts a `typical_consumption` variable.

If you explore the `elec_other` or `gas_other` variables, you'll see 12 key variables for storing nil rate values and 12 for variable rate values. These are:

- **df**: Direct fuel costs
- **cm**: Capacity market costs
- **aa**: Adjustment allowance
- **pc**: Policy costs
- **nc**: Network costs
- **oc**: Operating costs
- **smncc**: Smart metering net cost change
- **paac**: Payment method adjustment additional cost
- **pap**: Payment method adjustment percentage
- **ebit**: Earnings before interest and tax
- **hap**: Headroom allowance percentage
- **levelisation**: Levelisation

Of particular interest for rebalancing is the `pc` attributes `pc` and `pc_nil` which we can update with our own rebalanced levies to produce a bill under a particular rebalancing approach.

As with the `Levy` object, the tariff object allows you to calculate the fixed (nil), variable and total cost of a bill.

```{python}
# Get standing charge
print(elec_other.calculate_nil_consumption())

# Get variable charge (consumption in MWh)
print(elec_other.calculate_variable_consumption(2.7))

# Get total charge plus vat (fixed at 5%)
print(elec_other.calculate_total_consumption(2.7, vat=True)))
```

Incorportating rebalanced levies into the tariff object is straightforward, you simply update the `pc` and `pc_nil` attributes, for instance:

```{python}
# Update electricity tariff
elec_other.pc_nil = sum([levy.calculate_fixed_levy(True, False) for levy in rebalanced_levies])
elec_other.pc = sum([levy.calculate_variable_levy(1, 0) for levy in rebalanced_levies])

# Update gas tariff
gas_other.pc_nil = sum([levy.calculate_fixed_levy(False, True) for levy in rebalanced_levies])
gas_other.pc = sum([levy.calculate_variable_levy(0, 1) for levy in rebalanced_levies])
```

Then you can simply recalculate the tariff costs.

## Distributional Analysis

The Levy and Tariff objects allow you to input any consumption data and return costs.

One of the things we wanted to learn from rebalancing is not just how changes to levies affect the typical consumer, but how it might affect different consumer groups across the income distribution. To explore this, we've included some data for [Ofgem's energy consumer archetypes](https://www.ofgem.gov.uk/energy-policy-and-regulation/measuring-impact-our-policy-decisions). Relevant data is stored in the `config` folder and can we accessed with a data getter:

```{python}
from asf_levies_model.getters.load_data import ofgem_archetypes_data

df = ofgem_archetypes_data()
```

This loads a simple dataframe of the core Ofgem archetypes data which contains consumption data for each of the 24 archetypes. You enhance these archetypes as required by loading some additional data:

```{python}
from asf_levies_model.getters.load_data import (
    ofgem_archetypes_equivalised_income_deciles,
    ofgem_archetypes_net_income_deciles,
    ofgem_archetypes_retired_pension,
    ofgem_archetypes_scheme_eligibility)
```

These additional dataframe include archetype data on equivalised and net income decile membership, pension credit and retirement status, and eligibility for schemes like Warm Homes Discount.

## Project Development

The currently available code is a work in progress that is being actively developed. We provide no assurances that the code will continue to work in its current form as we enhance and develop the code base.

## Contributor guidelines

[Technical and working style guidelines](https://github.com/nestauk/ds-cookiecutter/blob/master/GUIDELINES.md)

---

<small><p>Project based on <a target="_blank" href="https://github.com/nestauk/ds-cookiecutter">Nesta's data science project template</a>
(<a href="http://nestauk.github.io/ds-cookiecutter">Read the docs here</a>).
</small>
