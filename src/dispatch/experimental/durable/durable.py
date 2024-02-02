from types import FunctionType, GeneratorType
from .generator import DurableGenerator
from .registry import register_function


def durable(fn):
    """A decorator that makes generators serializable."""
    return DurableFunction(fn)


class DurableFunction:
    """A wrapper for a generator function that wraps its generator instances
    with a DurableGenerator.

    Attributes:
        fn (FunctionType): A generator function.
        key (str): A key that uniquely identifies the function.
    """

    def __init__(self, fn: FunctionType):
        self.fn = fn
        self.key = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.fn(*args, **kwargs)
        if isinstance(result, GeneratorType):
            return DurableGenerator(result, self.key, args, kwargs)

        # TODO: support native coroutines
        raise NotImplementedError
