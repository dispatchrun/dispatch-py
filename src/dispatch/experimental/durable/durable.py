from types import FunctionType, GeneratorType

from .generator import DurableGenerator
from .registry import register_function


class DurableFunction:
    """A wrapper for a generator function that wraps its generator
    instances with a DurableGenerator. These wrapped generator instances
    are serializable.

    Attributes:
        fn: A generator function to wrap.
    """

    def __init__(self, fn: FunctionType):
        self.fn = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.fn.fn(*args, **kwargs)
        if not isinstance(result, GeneratorType):
            raise NotImplementedError(
                "only synchronous generator functions are supported"
            )
        return DurableGenerator(result, self.fn, args, kwargs)

    @property
    def __name__(self):
        return self.fn.fn.__name__


def durable(fn) -> DurableFunction:
    """Returns a "durable" function that creates serializable generators.

    Args:
        fn: A generator function.
    """
    return DurableFunction(fn)
