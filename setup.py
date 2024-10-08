"""asf_levies_model."""

from pathlib import Path
from setuptools import find_packages
from setuptools import setup


def read_lines(path):
    """Read lines of `path`."""
    with open(path) as f:
        return f.read().splitlines()


BASE_DIR = Path(__file__).parent


setup(
    name="asf_levies_model",
    long_description=open(BASE_DIR / "README.md").read(),
    install_requires=read_lines(BASE_DIR / "requirements.txt"),
    extras_require={"dev": read_lines(BASE_DIR / "requirements_dev.txt")},
    packages=find_packages(exclude=["docs"]),
    version="0.1.0",
    description="Analytical model of domestic energy bills and levies.",
    author="Nesta",
    license="MIT",
    package_data={
        "": [
            "base.yaml",
            "archetypes_equiv_income_deciles.pkl",
            "archetypes_headline_data.pkl",
            "archetypes_net_income_deciles.pkl",
            "archetypes_retired_pension.pkl",
            "archetypes_scheme_eligibility.pkl",
        ]
    },
    include_package_data=True,
)
