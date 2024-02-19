from dataclasses import dataclass
from types import coroutine
from typing import Any, Awaitable

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
def gather(*awaitables: Awaitable[Any]) -> list[Any]:  # type: ignore[misc]
    """Concurrently run a set of coroutines and block until all
    results are available. If any coroutine fails with an uncaught
    exception, it will be re-raised when awaiting a result here."""
    return (yield Gather(awaitables))


@dataclass(slots=True)
class Gather:
    awaitables: tuple[Awaitable[Any], ...]
