import logging
import pickle
import sys
from dataclasses import dataclass
from types import coroutine
from typing import Any

from dispatch.experimental.durable import durable
from dispatch.experimental.durable.function import DurableCoroutine, DurableFunction
from dispatch.proto import Call, CallResult, Error, Input, Output
from dispatch.status import Status, status_for_output

logger = logging.getLogger(__name__)


@coroutine
@durable
def poll(calls: list[Call]) -> list[CallResult]:  # type: ignore[misc]
    """Suspend the function with a set of Calls, instructing the
    orchestrator to resume the coroutine when call results are ready."""
    return (yield Poll(calls))


@coroutine
@durable
def exit(result: Any | None = None, tail_call: Call | None = None):
    """Exit exits a coroutine, with an optional result and
    optional tail call."""
    yield Exit(result, tail_call)


@dataclass
class Exit:
    result: Any | None
    tail_call: Call | None


@dataclass
class Poll:
    calls: list[Call]


def schedule(func: DurableFunction, input: Input) -> Output:
    """Schedule schedules a coroutine with the provided input."""
    try:
        # (Re)hydrate the coroutine.
        if input.is_first_call:
            logger.debug("starting coroutine")
            try:
                args, kwargs = input.input_arguments()
            except ValueError:
                raise ValueError("incorrect input for function")

            coro = func(*args, **kwargs)
            send = None
        else:
            logger.debug(
                "resuming coroutine with %d bytes of state and %d call result(s)",
                len(input.coroutine_state),
                len(input.call_results),
            )
            try:
                coroutine_state = pickle.loads(input.coroutine_state)
                if not isinstance(coroutine_state, CoroutineState):
                    raise ValueError("invalid coroutine state")
                if coroutine_state.version != sys.version:
                    raise ValueError(
                        f"coroutine state version mismatch: '{coroutine_state.version}' vs. current '{sys.version}'"
                    )
            except (pickle.PickleError, ValueError) as e:
                logger.warning("coroutine state is incompatible", exc_info=True)
                return Output.error(
                    Error.from_exception(e, status=Status.INCOMPATIBLE_STATE)
                )
            coro = coroutine_state.coroutine
            send = input.call_results

        # Run the coroutine until its next yield or return.
        try:
            directive = coro.send(send)
        except StopIteration as e:
            logger.debug("coroutine returned")
            return Output.value(e.value)

        # Handle directives that it yields.
        logger.debug("handling coroutine directive: %s", directive)
        match directive:
            case Exit():
                return Output.exit(
                    result=CallResult.from_value(directive.result),
                    tail_call=directive.tail_call,
                    status=status_for_output(directive.result),
                )

            case Poll():
                try:
                    coroutine_state = pickle.dumps(
                        CoroutineState(coroutine=coro, version=sys.version)
                    )
                except pickle.PickleError as e:
                    logger.error("coroutine could not be serialized", exc_info=True)
                    return Output.error(
                        Error.from_exception(e, status=Status.PERMANENT_ERROR)
                    )
                return Output.poll(state=coroutine_state, calls=directive.calls)

            case _:
                raise RuntimeError(f"coroutine unexpectedly yielded '{directive}'")

    except Exception as e:
        logger.exception(f"@dispatch.coroutine: '{func.__name__}' raised an exception")
        return Output.error(Error.from_exception(e))


@dataclass
class CoroutineState:
    """Serialized representation of a coroutine."""

    coroutine: DurableCoroutine
    version: str
