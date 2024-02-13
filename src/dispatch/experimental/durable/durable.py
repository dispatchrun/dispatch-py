from types import FunctionType, GeneratorType

from .generator import DurableGenerator
from .registry import register_function


class DurableFunction:
    """A wrapper for a generator functions and async functions that make
    their generator and coroutine instances serializable.

    Attributes:
        fn: A generator function or async function to wrap.
    """

    def __init__(self, fn: FunctionType):
        self.fn = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.fn.fn(*args, **kwargs)
        if not isinstance(result, GeneratorType):
            raise NotImplementedError(
                "only synchronous generator functions are supported"
            )
        return DurableGenerator(result, self.fn, list(args), kwargs)

    @property
    def __name__(self):
        return self.fn.fn.__name__


def durable(fn) -> DurableFunction:
    """Returns a "durable" function that creates serializable generators.

    Args:
        fn: A generator function.
    """
    return DurableFunction(fn)
