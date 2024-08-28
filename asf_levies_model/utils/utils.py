from typing import Callable


def _generate_docstring(inherited: str, new_params: list) -> Callable:
    """Decorator to update class docstrings."""

    def inner(obj):
        obj.__doc__ = inherited + "\n".join(new_params)
        return obj

    return inner
