from dataclasses import dataclass
from types import coroutine
from typing import Any, Awaitable, List, Tuple

from dispatch.experimental.durable import durable
from dispatch.proto import Call


@coroutine
@durable
def call(call: Call) -> Any:
    """Make an asynchronous function call and return its result. If the
    function call fails with an error, the error is raised."""
    return (yield call)


@coroutine
@durable
def gather(*awaitables: Awaitable[Any]) -> List[Any]:  # type: ignore[misc]
    """Alias for all."""
    return all(*awaitables)


@coroutine
@durable
def all(*awaitables: Awaitable[Any]) -> List[Any]:  # type: ignore[misc]
    """Concurrently run a set of coroutines, blocking until all coroutines
    return or any coroutine raises an error. If any coroutine fails with an
    uncaught exception, the exception will be re-raised here."""
    return (yield AllDirective(awaitables))


@coroutine
@durable
def any(*awaitables: Awaitable[Any]) -> List[Any]:  # type: ignore[misc]
    """Concurrently run a set of coroutines, blocking until any coroutine
    returns or all coroutines raises an error. If all coroutines fail with
    uncaught exceptions, the exception(s) will be re-raised here."""
    return (yield AnyDirective(awaitables))


@coroutine
@durable
def race(*awaitables: Awaitable[Any]) -> List[Any]:  # type: ignore[misc]
    """Concurrently run a set of coroutines, blocking until any coroutine
    returns or raises an error. If any coroutine fails with an uncaught
    exception, the exception will be re-raised here."""
    return (yield RaceDirective(awaitables))


@dataclass
class AllDirective:
    awaitables: Tuple[Awaitable[Any], ...]


@dataclass
class AnyDirective:
    awaitables: Tuple[Awaitable[Any], ...]


@dataclass
class RaceDirective:
    awaitables: Tuple[Awaitable[Any], ...]


class AnyException(RuntimeError):
    """Error indicating that all coroutines passed to any() failed
    with an exception."""

    __slots__ = ("exceptions",)

    def __init__(self, exceptions: List[Exception]):
        self.exceptions = exceptions

    def __str__(self):
        return f"{len(self.exceptions)} coroutine(s) failed with an exception"
