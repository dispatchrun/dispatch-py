from dataclasses import dataclass
from types import FunctionType
from typing import Any


def yields(type: Any):
    """Mark a function as a custom yield point."""

    def decorator(fn: FunctionType) -> FunctionType:
        fn._multicolor_yield_type = type  # type: ignore[attr-defined]
        return fn

    return decorator


class YieldType:
    """Base class for yield types."""


@dataclass
class CustomYield(YieldType):
    """A yield from a function marked with @yields."""

    type: Any
    args: list[Any]
    kwargs: dict[str, Any] | None = None


@dataclass
class GeneratorYield(YieldType):
    """A yield from a generator."""

    value: Any = None
