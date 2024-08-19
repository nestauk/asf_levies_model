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

# %%
import pandas
import matplotlib.pyplot as pyplot
from matplotlib.lines import Line2D
from datetime import timedelta
from dateutil.relativedelta import relativedelta

# %% [markdown]
# ## Datasets
#
# ### Sources of consumption data
# We're interested in 4 different sources of consumption data:
# 1. Electricity and gas consumption captured in ofgem annex 4 for ECO.
# 2. DUKES electricity (5.5) and gas (4.2) sales.
# 3. DESNZ Annex F final energy demand from Energy and emissions projections: 2022 to 2040.
# 4. Subnational consumption data for electricity and non-weather corrected gas.
#
# Relevant to rebalancing levies, we're interested in both the absolute difference between different estimates as well as differences in the ratio between electricity and gas.
#
# Absolute differences have the potential to affect estimates of revenue derived from per unit consumption levy rates, while differences in the relative consumption of electricity to gas could affect the reapportionment of the levy.

# %%
# Eco Annex 4

periods = pandas.Series(
    [
        "April 2015 – September 2015",
        "October 2015- March 2016",
        "April 2016-September 2016",
        "October 2016-March 2017",
        "April 2017 - September 2017",
        "October 2017 - March 2018",
        "April 2018 - September 2018",
        "October 2018 - March 2019",
        "January 2019 - March 2019",
        "April 2019 - September 2019",
        "October 2019 - March 2020",
        "April 2020 - September 2020",
        "October 2020 - March 2021",
        "April 2021 - September 2021",
        "October 2021 - March 2022",
        "April 2022 - September 2022",
        "October 2022 - December 2022",
        "January 2023 - March 2023",
        "April 2023 - June 2023",
        "July 2023 - September 2023",
        "October 2023 - December 2023",
        "January 2024 - March 2024",
        "April 2024 - June 2024",
    ],
    name="28AD Charge Restriction Period",
)

gas = pandas.Series(
    [
        300_797_469,
        300_797_469,
        292_794_167,
        292_794_167,
        296_106_141,
        296_106_141,
        275_805_404,
        279_759_249,
        279_759_249,
        279_759_249,
        272_343_335,
        272_343_335,
        286_200_367,
        286_200_367,
        291_212_009,
        291_212_009,
        296_075_775,
        296_075_775,
        314_163_650,
        314_163_650,
        314_163_650,
        314_163_650,
        271_672_723,
    ],
    name="Supply volumes of obligated suppliers - gas (MWh supplied)",
)

electricity = pandas.Series(
    [
        102_351_089,
        102_351_089,
        103_688_990,
        103_688_990,
        103_762_504,
        103_762_504,
        98_269_992,
        95_868_334,
        95_868_334,
        95_868_334,
        89_570_567,
        89_570_567,
        90_304_045,
        90_304_045,
        94_679_766,
        94_679_766,
        98_069_558,
        98_069_558,
        85_288_068,
        85_288_068,
        85_288_068,
        85_288_068,
        93_503_455,
    ],
    name="Supply volumes of obligated suppliers - electricity (MWh supplied)",
)

# %%
eco = pandas.concat([periods, gas, electricity], axis=1).assign(
    start=lambda df: pandas.to_datetime(
        df["28AD Charge Restriction Period"].str.split("\s?-\s?|\s?–\s?", expand=True)[
            0
        ],
        format="%B %Y",
    ),
    end=lambda df: pandas.to_datetime(
        df["28AD Charge Restriction Period"].str.split("\s?-\s?|\s?–\s?", expand=True)[
            1
        ],
        format="%B %Y",
    ).apply(lambda date: date + relativedelta(months=+1) + relativedelta(days=-1)),
)

# %%
f, (ax1, ax2) = pyplot.subplots(1, 2, figsize=(14, 5))

# ax1 reported supply volumes
ax1.bar(
    x=eco["start"],
    height=eco["Supply volumes of obligated suppliers - gas (MWh supplied)"],
    width=eco["end"] - eco["start"],
    align="edge",
    ec="k",
    fc="indianred",
    alpha=0.6,
    label="Gas",
)

ax1.bar(
    x=eco["start"],
    height=eco["Supply volumes of obligated suppliers - electricity (MWh supplied)"],
    width=eco["end"] - eco["start"],
    align="edge",
    ec="b",
    fc="skyblue",
    label="Electricity",
)

ax1.set_xlabel("Year")
ax1.set_ylabel("Supply Volume, MWh Supplied")
ax1.legend(loc=4)

# ax2 supply ratio
eco["share"] = eco[
    "Supply volumes of obligated suppliers - electricity (MWh supplied)"
] / (
    eco["Supply volumes of obligated suppliers - electricity (MWh supplied)"]
    + eco["Supply volumes of obligated suppliers - gas (MWh supplied)"]
)

line_share = Line2D(
    eco[["start", "end"]].to_numpy().flatten(),
    eco[["share", "share"]].to_numpy().flatten(),
)

ax2.add_line(line_share)

ax2.set_xlim(ax1.get_xlim())
ax2.set_xticks(ax1.get_xticks())
ax2.set_xticklabels(ax1.get_xticklabels())
ax2.set_ylim([0, 0.5])
ax2.grid()
ax2.set_xlabel("Year")
ax2.set_ylabel("Electricity Share of Supply")

# %%
# Desnz Annex F
# Final energy demand

year = pandas.period_range(
    start=pandas.Period("2000", freq="Y"), end=pandas.Period("2040", freq="Y"), freq="Y"
)
res_elec = pandas.Series(
    [
        9_617,
        9_917,
        10_319,
        10_576,
        10_679,
        10_809,
        10_723,
        10_583,
        10_301,
        10_193,
        10_218,
        9_595,
        9_859,
        9_752,
        9_293,
        9_266,
        9_288,
        9_060,
        9_034,
        8_918,
        9_284,
        9_411,
        9_047,
        8_604,
        8_373,
        8_366,
        8_422,
        8_558,
        8_718,
        8_941,
        9_204,
        9_327,
        9_522,
        9_688,
        9_858,
        10_027,
        10_197,
        10_381,
        10_573,
        10_782,
        11_025,
    ],
    name="Residential Electricity, ktoe",
)
res_gas = pandas.Series(
    [
        31_806,
        32_625,
        32_362,
        33_232,
        34_085,
        32_836,
        31_550,
        30_341,
        30_916,
        29_682,
        33_499,
        26_556,
        29_508,
        29_622,
        24_393,
        25_587,
        26_301,
        25_372,
        26_249,
        25_255,
        25_500,
        27_377,
        23_348,
        21_764,
        22_339,
        22_427,
        22_377,
        22_480,
        22_671,
        23_180,
        23_719,
        24_421,
        24_737,
        24_943,
        25_111,
        25_325,
        25_546,
        25_757,
        25_941,
        26_116,
        26_317,
    ],
    name="Residential Natural Gas, ktoe",
)

total_elec = pandas.Series(
    [
        27_939,
        28_206,
        28_281,
        28_534,
        29_143,
        29_979,
        29_683,
        29_376,
        29_390,
        27_664,
        28_276,
        27_333,
        27_367,
        27_196,
        26_036,
        26_098,
        26_148,
        25_773,
        25_845,
        25_455,
        24_134,
        24_646,
        24_339,
        23_726,
        23_576,
        23_863,
        24_166,
        24_548,
        25_003,
        25_538,
        26_177,
        26_688,
        27_304,
        27_906,
        28_489,
        29_085,
        29_711,
        30_357,
        31_039,
        31_634,
        32_241,
    ],
    name="Total Electricity, ktoe",
)

total_gas = pandas.Series(
    [
        57_077,
        57_814,
        55_234,
        56_701,
        57_080,
        55_384,
        52_633,
        49_961,
        51_502,
        46_828,
        51_630,
        42_907,
        46_853,
        47_429,
        40_427,
        41_896,
        43_058,
        42_171,
        43_144,
        42_419,
        41_550,
        44_587,
        39_748,
        37_827,
        37_979,
        37_840,
        37_853,
        38_030,
        38_323,
        38_907,
        39_500,
        40_289,
        40_693,
        41_013,
        41_307,
        41_712,
        42_168,
        42_675,
        43_107,
        43_505,
        43_927,
    ],
    name="Total Natural Gas, ktoe",
)

# %%
desnz = pandas.concat(
    [res_gas, res_elec, total_gas, total_elec], levels=year, axis=1
).assign(
    **{
        "Residential Natural Gas, MWh": lambda df: df["Residential Natural Gas, ktoe"]
        * 11630,
        "Residential Electricity, MWh": lambda df: df["Residential Electricity, ktoe"]
        * 11630,
        "Total Natural Gas, MWh": lambda df: df["Total Natural Gas, ktoe"] * 11630,
        "Total Electricity, MWh": lambda df: df["Total Electricity, ktoe"] * 11630,
    }
)
desnz.index = year

# %%
f, (ax1, ax2) = pyplot.subplots(1, 2, figsize=(12, 5))

# ax1
ax1.plot(
    desnz.index.to_timestamp(),
    desnz["Residential Natural Gas, MWh"],
    color="coral",
    label="Residential Natural Gas",
)
ax1.plot(
    desnz.index.to_timestamp(),
    desnz["Residential Electricity, MWh"],
    color="mediumaquamarine",
    label="Residential Electricity",
)
ax1.plot(
    desnz.index.to_timestamp(),
    desnz["Total Natural Gas, MWh"],
    color="firebrick",
    label="Total Natural Gas",
)
ax1.plot(
    desnz.index.to_timestamp(),
    desnz["Total Electricity, MWh"],
    color="seagreen",
    label="Total Electricity",
)

ax1.grid()
ax1.set_xlabel("Year")
ax1.set_ylabel("Final Energy Demand, MWh")
ax1.legend()
ax1.set_ylim([0, desnz["Total Natural Gas, MWh"].max() + 50_000_000])

# ax2
desnz["res_share"] = desnz["Residential Electricity, MWh"] / (
    desnz["Residential Natural Gas, MWh"] + desnz["Residential Electricity, MWh"]
)
desnz["total_share"] = desnz["Total Electricity, MWh"] / (
    desnz["Total Natural Gas, MWh"] + desnz["Total Electricity, MWh"]
)

ax2.plot(
    desnz.index.to_timestamp(),
    desnz["res_share"],
    label="Residential Electricity Share of Demand",
)
ax2.plot(
    desnz.index.to_timestamp(),
    desnz["total_share"],
    label="Total Electricity Share of Demand",
)
ax2.set_ylim([0, 0.5])
ax2.grid()
ax2.set_ylabel("Share of Final Demand")
ax2.legend()

# %%
# Dukes

year = pandas.period_range(
    start=pandas.Period("1996", freq="Y"), end=pandas.Period("2023", freq="Y"), freq="Y"
)

# Table 5.5
electricity_sales = pandas.Series(
    [
        300_585,
        300_756,
        303_484,
        308_358,
        314_665,
        321_067,
        319_800,
        324_333,
        323_714,
        331_273,
        329_231,
        330_246,
        331_870,
        313_784,
        319_920,
        308_033,
        308_408,
        306_748,
        291_153,
        290_039,
        288_331,
        281_299,
        281_279,
        276_971,
        260_982,
        266_674,
        250_457,
        247_751,
    ],
    name="UK Electricity Sales, GWh",
)
# Table 5.2
electricity_domestic = pandas.Series(
    [
        None,
        None,
        109_410_000,
        110_308_000,
        111_842_000,
        115_337_000,
        120_014_410,
        123_000_760,
        124_200_470,
        125_711_140,
        124_703_920,
        123_076_030,
        119_800_000,
        118_540_790,
        118_831_950,
        111_586_420,
        114_662_630,
        113_412_470,
        108_076_100,
        107_763_850,
        108_025_040,
        105_322_501,
        105_961_225,
        103_978_956,
        107_633_308,
        107_145_304,
        95_416_677,
        92_555_754,
    ],
    name="UK Domestic Electricity Consumption, MWh",
)

# Table 4.2
gas_domestic_consumption = pandas.Series(
    [
        375_841,
        345_532,
        355_895,
        358_066,
        369_909,
        379_426,
        376_372,
        386_486,
        396_411,
        381_879,
        366_928,
        352_868,
        359_554,
        345_199,
        389_596,
        308_841,
        343_180,
        344_501,
        283_691,
        297_582,
        302_375,
        295_773,
        302_902,
        292_429,
        300_206,
        318_796,
        259_091,
        237_100,
    ],
    name="UK Domestic Gas Consumption, GWh",
)

gas_total_final_consumption = pandas.Series(
    [
        671_042,
        640_819,
        661_580,
        654_312,
        678_142,
        683_753,
        653_151,
        669_457,
        673_860,
        652_024,
        620_035,
        591_274,
        607_178,
        551_492,
        608_551,
        504_961,
        550_672,
        557_201,
        475_601,
        492_514,
        496_863,
        492_102,
        509_961,
        496_604,
        490_812,
        517_183,
        438_991,
        414_376,
    ],
    name="UK Total Final Gas Consumption, GWh",
)

# %%
dukes = pandas.concat(
    [
        electricity_domestic,
        electricity_sales,
        gas_domestic_consumption,
        gas_total_final_consumption,
    ],
    axis=1,
).assign(
    **{
        "UK Electricity Sales, MWh": lambda df: df["UK Electricity Sales, GWh"] * 1_000,
        "UK Domestic Gas Consumption, MWh": lambda df: df[
            "UK Domestic Gas Consumption, GWh"
        ]
        * 1_000,
        "UK Total Final Gas Consumption, MWh": lambda df: df[
            "UK Total Final Gas Consumption, GWh"
        ]
        * 1_000,
    }
)

dukes.index = year

# %%
f, (ax1, ax2) = pyplot.subplots(1, 2, figsize=(12, 5))

# ax1
ax1.plot(
    dukes.index.to_timestamp(),
    dukes["UK Domestic Gas Consumption, MWh"],
    color="coral",
    label="Domestic Natural Gas",
)
ax1.plot(
    dukes.index.to_timestamp(),
    dukes["UK Domestic Electricity Consumption, MWh"],
    color="mediumaquamarine",
    label="Domestic Electricity",
)
ax1.plot(
    dukes.index.to_timestamp(),
    dukes["UK Total Final Gas Consumption, MWh"],
    color="firebrick",
    label="Total Natural Gas",
)
ax1.plot(
    dukes.index.to_timestamp(),
    dukes["UK Electricity Sales, MWh"],
    color="seagreen",
    label="Total Electricity",
)

ax1.grid()
ax1.set_xlabel("Year")
ax1.set_ylabel("Final Energy Consumption, MWh")
ax1.legend()
ax1.set_ylim([0, dukes["UK Total Final Gas Consumption, MWh"].max() + 50_000_000])

# ax2
dukes["res_share"] = dukes["UK Domestic Electricity Consumption, MWh"] / (
    dukes["UK Domestic Gas Consumption, MWh"]
    + dukes["UK Domestic Electricity Consumption, MWh"]
)
dukes["total_share"] = dukes["UK Electricity Sales, MWh"] / (
    dukes["UK Total Final Gas Consumption, MWh"] + dukes["UK Electricity Sales, MWh"]
)

ax2.plot(
    dukes.index.to_timestamp(),
    dukes["res_share"],
    label="Domestic Electricity Share of Consumption",
)
ax2.plot(
    dukes.index.to_timestamp(),
    dukes["total_share"],
    label="Total Electricity Share of Consumption",
)
ax2.set_ylim([0, 0.5])
ax2.grid()
ax2.set_ylabel("Share of Final Demand")
ax2.legend()

# %%
# Subnational Consumption

year = pandas.period_range(
    start=pandas.Period("2005", freq="Y"), end=pandas.Period("2022", freq="Y"), freq="Y"
)

# Gas, non-weather corrected (including unallocated)
domestic_gas = pandas.Series(
    [
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        317_453_337,
        311_573_517,
        330_173_277,
        311_793_337,
        324_462_254,
        343_537_020,
        296_857_376,
        265_197_947,
    ],
    name="Domestic Gas Consumption, GB MWh",
)
total_gas = pandas.Series(
    [
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        499_462_941,
        486_733_193,
        512_816_392,
        492_104_358,
        501_297_907,
        528_117_199,
        473_084_053,
        435_369_123,
    ],
    name="Total Gas Consumption, GB MWh",
)

# Electricity
domestic_electricity = pandas.Series(
    [
        119_424_904,
        117_816_503,
        117_126_209,
        112_530_494,
        112_289_258,
        112_855_507,
        111_321_038,
        110_065_689,
        108_419_925,
        109_179_853,
        108_346_298,
        106_431_188,
        105_374_661,
        103_178_403,
        102_926_400,
        108_608_382,
        102_581_056,
        94_200_366,
    ],
    name="Domestic Electricity Consumption, GB MWh",
)

total_electricity = pandas.Series(
    [
        320_314_371,
        317_831_779,
        309_669_466,
        304_624_972,
        295_275_316,
        297_961_283,
        286_360_702,
        290_892_534,
        289_975_577,
        292_192_085,
        287_536_447,
        277_606_701,
        279_662_554,
        277_009_572,
        272_588_575,
        257_215_525,
        258_871_876,
        250_020_739,
    ],
    name="Total Electricity Consumption, GB MWh",
)

# %%
subnat = pandas.concat(
    [domestic_gas, total_gas, domestic_electricity, total_electricity], axis=1
)
subnat.index = year

# %%
f, (ax1, ax2) = pyplot.subplots(1, 2, figsize=(12, 5))

# ax1
ax1.plot(
    subnat.index.to_timestamp(),
    subnat["Domestic Gas Consumption, GB MWh"],
    color="coral",
    label="Domestic Natural Gas",
)
ax1.plot(
    subnat.index.to_timestamp(),
    subnat["Domestic Electricity Consumption, GB MWh"],
    color="mediumaquamarine",
    label="Domestic Electricity",
)
ax1.plot(
    subnat.index.to_timestamp(),
    subnat["Total Gas Consumption, GB MWh"],
    color="firebrick",
    label="Total Natural Gas",
)
ax1.plot(
    subnat.index.to_timestamp(),
    subnat["Total Electricity Consumption, GB MWh"],
    color="seagreen",
    label="Total Electricity",
)

ax1.grid()
ax1.set_xlabel("Year")
ax1.set_ylabel("Final Energy Consumption, MWh")
ax1.legend()
ax1.set_ylim([0, subnat["Total Gas Consumption, GB MWh"].max() + 50_000_000])

# ax2
subnat["res_share"] = subnat["Domestic Electricity Consumption, GB MWh"] / (
    subnat["Domestic Gas Consumption, GB MWh"]
    + subnat["Domestic Electricity Consumption, GB MWh"]
)
subnat["total_share"] = subnat["Total Electricity Consumption, GB MWh"] / (
    subnat["Total Gas Consumption, GB MWh"]
    + subnat["Total Electricity Consumption, GB MWh"]
)

ax2.plot(
    subnat.index.to_timestamp(),
    subnat["res_share"],
    label="Domestic Electricity Share of Consumption",
)
ax2.plot(
    subnat.index.to_timestamp(),
    subnat["total_share"],
    label="Total Electricity Share of Consumption",
)
ax2.set_ylim([0, 0.5])
ax2.grid()
ax2.set_ylabel("Share of Consumption")
ax2.legend()

# %% [markdown]
# ## Sources of Customer Numbers Data
#
# The warm homes discount gives a total customer number as: gas only + electricity only + dual fuel + dual fuel.
# - Annex 4 reports only the total sum, not the breakdown by fuel.
#
# Subnational consumption provides meter numbers separately for gas and electricity.

# %%
# WHD
periods = pandas.Series(
    [
        "April 2015 – September 2015",
        "October 2015- March 2016",
        "April 2016-September 2016",
        "October 2016-March 2017",
        "April 2017 - September 2017",
        "October 2017 - March 2018",
        "April 2018 - September 2018",
        "October 2018 - March 2019",
        "January 2019 - March 2019",
        "April 2019 - September 2019",
        "October 2019 - March 2020",
        "April 2020 - September 2020",
        "October 2020 - March 2021",
        "April 2021 - September 2021",
        "October 2021 - March 2022",
        "April 2022 - September 2022",
        "October 2022 - December 2022",
        "January 2023 - March 2023",
        "April 2023 - June 2023",
        "July 2023 - September 2023",
        "October 2023 - December 2023",
        "January 2024 - March 2024",
        "April 2024 - June 2024",
    ],
    name="28AD Charge Restriction Period",
)

customers = pandas.Series(
    [
        48_804_601,
        48_804_601,
        48_793_487,
        48_793_487,
        49_081_370,
        49_081_370,
        47_655_700,
        47_655_700,
        47_655_700,
        47_655_700,
        48_171_495,
        48_171_495,
        50_203_694,
        50_203_694,
        50_687_416,
        50_687_416,
        52_258_752,
        52_258_752,
        52_919_620,
        52_919_620,
        52_919_620,
        52_919_620,
        50_690_856,
    ],
    name="customers",
)

# %%
whd = pandas.concat([periods, customers], axis=1).assign(
    start=lambda df: pandas.to_datetime(
        df["28AD Charge Restriction Period"].str.split("\s?-\s?|\s?–\s?", expand=True)[
            0
        ],
        format="%B %Y",
    ),
    end=lambda df: pandas.to_datetime(
        df["28AD Charge Restriction Period"].str.split("\s?-\s?|\s?–\s?", expand=True)[
            1
        ],
        format="%B %Y",
    ).apply(lambda date: date + relativedelta(months=+1) + relativedelta(days=-1)),
)

# %%
f, ax = pyplot.subplots(figsize=(8, 5))

# ax1 reported customers
ax.bar(
    x=whd["start"],
    height=whd["customers"],
    width=whd["end"] - whd["start"],
    align="edge",
    ec="k",
    fc="indianred",
    alpha=0.6,
    label="Customers",
)

ax.set_xlabel("Year")
ax.set_ylabel("Customer Numbers, Obligated Suppliers")

# %%
# Subnational consumption

year = pandas.period_range(
    start=pandas.Period("2005", freq="Y"), end=pandas.Period("2022", freq="Y"), freq="Y"
)

# Electricity
domestic_electricity_meters = (
    pandas.Series(
        [
            25948.94,
            26433.816,
            26670.293,
            26805.185,
            27046.86,
            27208.89,
            27301.241,
            27410.484,
            27521.12,
            27707.802,
            27510.375,
            27717.055,
            27896.901,
            28120.916,
            28367.727,
            28580.72,
            28849.662,
            29_078.77,
        ],
        name="Domestic Electricity Meters",
    )
    * 1_000
)
total_electricity_meters = (
    pandas.Series(
        [
            28394.95,
            28874.46,
            29105.166,
            29212.125,
            29446.285,
            29591.037,
            29687.12,
            29808.273,
            29925.189,
            30189.732,
            29875.844,
            30084.429,
            30299.756,
            30559.569,
            30806.242,
            31016.78,
            31297.14,
            31_537.6,
        ],
        name="Total Electricity Meters",
    )
    * 1_000
)
# Gas, weather corrected data.
domestic_gas_meters = (
    pandas.Series(
        [
            21594.972,
            21884.182,
            22223.706,
            22327.126,
            22584.216,
            22718.973,
            22838.766,
            22959.854,
            23074.102,
            23234.729,
            23090.283,
            23251.506,
            23623.103,
            23879.877,
            23995.287,
            24155.745,
            24336.113,
            24503.683,
        ],
        name="Domestic Gas Meters",
    )
    * 1_000
)

total_gas_meters = (
    pandas.Series(
        [
            21993.159,
            22263.115,
            22575.016,
            22651.353,
            22872.945,
            23003.112,
            23113.497,
            23231.668,
            23346.77,
            23505.482,
            23353.297,
            23515.522,
            23891.002,
            24158.412,
            24260.623,
            24421.844,
            24603.914,
            24750.358,
        ],
        name="Total Gas Meters",
    )
    * 1_000
)

# %%
subnat_meters = pandas.concat(
    [
        domestic_electricity_meters,
        total_electricity_meters,
        domestic_gas_meters,
        total_gas_meters,
    ],
    axis=1,
)
subnat_meters.index = year

# %%
f, (ax1, ax2) = pyplot.subplots(1, 2, figsize=(12, 5))

# ax1
ax1.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["Domestic Gas Meters"],
    color="coral",
    label="Domestic Natural Gas Meters",
)
ax1.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["Domestic Electricity Meters"],
    color="mediumaquamarine",
    label="Domestic Electricity Meters",
)
ax1.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["Total Gas Meters"],
    color="firebrick",
    label="Total Natural Gas Meters",
)
ax1.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["Total Electricity Meters"],
    color="seagreen",
    label="Total Electricity Meters",
)

ax1.grid()
ax1.set_xlabel("Year")
ax1.set_ylabel("Number of Meter Points")
ax1.legend()
ax1.set_ylim([0, subnat_meters["Total Electricity Meters"].max() + 5_000_000])

# ax2
subnat_meters["res_share"] = subnat_meters["Domestic Electricity Meters"] / (
    subnat_meters["Domestic Gas Meters"] + subnat_meters["Domestic Electricity Meters"]
)
subnat_meters["total_share"] = subnat_meters["Total Electricity Meters"] / (
    subnat_meters["Total Gas Meters"] + subnat_meters["Total Electricity Meters"]
)

ax2.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["res_share"],
    label="Domestic Electricity Share of Meters",
)
ax2.plot(
    subnat_meters.index.to_timestamp(),
    subnat_meters["total_share"],
    label="Total Electricity Share of Meters",
)
ax2.set_ylim([0, 0.65])
ax2.grid()
ax2.set_ylabel("Share of Meter Points")
ax2.legend()
