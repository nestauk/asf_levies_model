import pandas as pd
from typing import Callable, Dict


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


def _dictionary_depth(d: dict) -> int:
    """Convenience function to calculate the depth of a dictionary."""
    if not isinstance(d, dict) or not d:
        return 0
    else:
        return max(_dictionary_depth(v) for k, v in d.items()) + 1


def create_eligibility_group_sizes_dictionary(
    df: pd.DataFrame, group_name_col: str, total_size_col: str, eligible_size_col: str
) -> Dict:
    """Helper function to construct a dictionary for eligibility/ineligibility group sizes. True key corresponds to eligible size and False key for ineligible size."""
    return {
        row[group_name_col]: {
            True: row[eligible_size_col],
            False: row[total_size_col] - row[eligible_size_col],
        }
        for _, row in df.iterrows()
    }
