from types import FunctionType, GeneratorType

from .generator import DurableGenerator
from .registry import register_function


class DurableFunction:
    """A wrapper for a generator function that wraps its generator instances
    with a DurableGenerator.

    Attributes:
        fn: A generator function.
        key: A key that uniquely identifies the function.
    """

    def __init__(self, fn: FunctionType):
        self.fn = fn
        self.key = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.fn(*args, **kwargs)
        if not isinstance(result, GeneratorType):
            raise NotImplementedError(
                "only synchronous generator functions are supported"
            )
        return DurableGenerator(result, self.key, args, kwargs)


def durable(fn) -> DurableFunction:
    """Returns a "durable" function that creates serializable generators.

    Args:
        fn: A generator function.
    """
    return DurableFunction(fn)
