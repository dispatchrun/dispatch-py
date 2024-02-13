from dataclasses import dataclass
from types import FunctionType
from typing import Any


def yields(type: Any):
    """Returns a decorator that marks functions as a type of yield.

    Args:
        type: Opaque type for this yield.
    """

    def decorator(fn: FunctionType) -> FunctionType:
        fn._multicolor_yield_type = type  # type: ignore[attr-defined]
        return fn

    return decorator


def no_yields(fn):
    """Decorator that hints that a function (and anything called
    recursively) does not yield."""
    fn._multicolor_no_yields = True  # type: ignore[attr-defined]
    return fn


class YieldType:
    """Base class for yield types."""


@dataclass
class CustomYield(YieldType):
    """A yield from a function marked with @yields.

    Attributes:
        type: The type of yield that was specified in the @yields decorator.
        args: Positional arguments to the function call.
        kwargs: Keyword arguments to the function call.
    """

    type: Any
    args: list[Any]
    kwargs: dict[str, Any] | None = None

    def kwarg(self, name, pos) -> Any:
        if self.kwargs is None:
            return self.args[pos]
        try:
            return self.kwargs[name]
        except KeyError:
            return self.args[pos]


@dataclass
class GeneratorYield(YieldType):
    """A yield from a generator.

    Attributes:
        value: The value that was yielded from the generator.
    """

    value: Any = None
