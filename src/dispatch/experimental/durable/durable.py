from types import FunctionType, GeneratorType
from .generator import DurableGenerator
from .registry import register_function


def durable(fn):
    """A decorator for a generator that makes it pickle-able."""
    return DurableFunction(fn)


class DurableFunction:
    """A durable generator function that can be pickled."""

    def __init__(self, fn: FunctionType):
        self.fn = fn
        self.key = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.fn(*args, **kwargs)
        if isinstance(result, GeneratorType):
            return DurableGenerator(result, self.key, args, kwargs)

        # TODO: support native coroutines
        raise NotImplementedError
