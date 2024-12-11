import pandas as pd
from typing import Callable


class PriceCapPeriod(pd.Interval):
    """Subclassing the pandas interval object so it outputs a nice repr."""

    def __init__(self, left, right, closed):
        super().__init__(left, right, closed)

    def __repr__(self):
        return f"{self.left.strftime('%d/%m/%Y')} - {self.right.strftime('%d/%m/%Y')}"


def _generate_docstring(inherited: str, new_params: list) -> Callable:
    """Decorator to update class docstrings."""

    def inner(obj):
        obj.__doc__ = inherited + "\n".join(new_params)
        return obj

    return inner
