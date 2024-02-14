from types import (
    AsyncGeneratorType,
    CodeType,
    CoroutineType,
    FrameType,
    FunctionType,
    GeneratorType,
    TracebackType,
)
from typing import Any, Coroutine, Generator, TypeVar, cast

from .registry import RegisteredFunction, register_function
from .serializable import Serializable


class DurableFunction:
    """A wrapper for generator functions and async functions that make
    their generator and coroutine instances serializable."""

    def __init__(self, fn: FunctionType):
        self.registered_fn = register_function(fn)

    def __call__(self, *args, **kwargs):
        result = self.registered_fn.fn(*args, **kwargs)

        if isinstance(result, GeneratorType):
            return DurableGenerator(result, self.registered_fn, *args, **kwargs)
        elif isinstance(result, CoroutineType):
            return DurableCoroutine(result, self.registered_fn, *args, **kwargs)
        elif isinstance(result, AsyncGeneratorType):
            raise NotImplementedError(
                "only synchronous generator functions are supported at this time"
            )
        else:
            raise ValueError(
                "@durable function did not return a generator or coroutine"
            )

    @property
    def __name__(self):
        return self.registered_fn.fn.__name__


def durable(fn) -> DurableFunction:
    """Returns a "durable" function that creates serializable
    generators or coroutines.

    Args:
        fn: A generator function or async function.
    """
    return DurableFunction(fn)


_YieldT = TypeVar("_YieldT", covariant=True)
_SendT = TypeVar("_SendT", contravariant=True)
_ReturnT = TypeVar("_ReturnT", covariant=True)


class DurableGenerator(Serializable, Generator[_YieldT, _SendT, _ReturnT]):
    """A wrapper for a generator that makes it serializable (can be pickled).
    Instances behave like the generators they wrap."""

    def __init__(
        self,
        generator: GeneratorType,
        registered_fn: RegisteredFunction,
        *args: Any,
        coro_await: bool = False,
        **kwargs: Any,
    ):
        self.generator = generator
        Serializable.__init__(
            self, generator, registered_fn, *args, coro_await=coro_await, **kwargs
        )

    def __iter__(self) -> Generator[_YieldT, _SendT, _ReturnT]:
        return self

    def __next__(self) -> _YieldT:
        return next(self.generator)

    def send(self, send: _SendT) -> _YieldT:
        return self.generator.send(send)

    def throw(self, typ, val=None, tb: TracebackType | None = None) -> _YieldT:
        return self.generator.throw(typ, val, tb)

    def close(self) -> None:
        self.generator.close()

    def __setstate__(self, state):
        Serializable.__setstate__(self, state)
        self.generator = cast(GeneratorType, self.g)

    @property
    def gi_running(self) -> bool:
        return self.generator.gi_running

    @property
    def gi_suspended(self) -> bool:
        return self.generator.gi_suspended

    @property
    def gi_code(self) -> CodeType:
        return self.generator.gi_code

    @property
    def gi_frame(self) -> FrameType:
        return self.generator.gi_frame

    @property
    def gi_yieldfrom(self) -> GeneratorType | None:
        return self.generator.gi_yieldfrom


class DurableCoroutine(Serializable, Coroutine[_YieldT, _SendT, _ReturnT]):
    """A wrapper for a coroutine that makes it serializable (can be pickled).
    Instances behave like the coroutines they wrap."""

    def __init__(
        self,
        coroutine: CoroutineType,
        registered_fn: RegisteredFunction,
        *args: Any,
        **kwargs: Any,
    ):
        self.coroutine = coroutine
        Serializable.__init__(self, coroutine, registered_fn, *args, **kwargs)

    def __await__(self) -> Generator[Any, None, _ReturnT]:
        coroutine_wrapper = self.coroutine.__await__()
        generator = cast(GeneratorType, coroutine_wrapper)
        durable_coroutine_wrapper: Generator[Any, None, _ReturnT] = DurableGenerator(
            generator, self.registered_fn, *self.args, coro_await=True, **self.kwargs
        )
        return durable_coroutine_wrapper

    def send(self, send: _SendT) -> _YieldT:
        return self.coroutine.send(send)

    def throw(self, typ, val=None, tb: TracebackType | None = None) -> _YieldT:
        return self.coroutine.throw(typ, val, tb)

    def close(self) -> None:
        self.coroutine.close()

    def __setstate__(self, state):
        Serializable.__setstate__(self, state)
        self.coroutine = cast(CoroutineType, self.g)

    @property
    def cr_running(self) -> bool:
        return self.coroutine.cr_running

    @property
    def cr_suspended(self) -> bool:
        return self.coroutine.cr_suspended

    @property
    def cr_code(self) -> CodeType:
        return self.coroutine.cr_code

    @property
    def cr_frame(self) -> FrameType:
        return self.coroutine.cr_frame

    @property
    def cr_await(self) -> Any | None:
        return self.coroutine.cr_await

    @property
    def cr_origin(self) -> tuple[tuple[str, int, str], ...] | None:
        return self.coroutine.cr_origin
