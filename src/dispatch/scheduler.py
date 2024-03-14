import logging
import pickle
import sys
from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeAlias

from dispatch.coroutine import Gather
from dispatch.error import IncompatibleStateError
from dispatch.experimental.durable.function import DurableCoroutine, DurableGenerator
from dispatch.proto import Call, Error, Input, Output
from dispatch.status import Status

logger = logging.getLogger(__name__)

CallID: TypeAlias = int
CoroutineID: TypeAlias = int
CorrelationID: TypeAlias = int


@dataclass(slots=True)
class CoroutineResult:
    """The result from running a coroutine to completion."""

    coroutine_id: CoroutineID
    value: Any | None = None
    error: Exception | None = None


@dataclass(slots=True)
class CallResult:
    """The result of an asynchronous function call."""

    call_id: CallID
    value: Any | None = None
    error: Exception | None = None


class Future(Protocol):
    def add_result(self, result: CallResult | CoroutineResult): ...

    def add_error(self, error: Exception): ...

    def ready(self) -> bool: ...

    def error(self) -> Exception | None: ...

    def value(self) -> Any: ...


@dataclass(slots=True)
class CallFuture:
    """A future result of a dispatch.coroutine.call() operation."""

    result: CallResult | None = None
    first_error: Exception | None = None

    def add_result(self, result: CallResult | CoroutineResult):
        assert isinstance(result, CallResult)
        if self.result is None:
            self.result = result
        if result.error is not None and self.first_error is None:
            self.first_error = result.error

    def add_error(self, error: Exception):
        if self.first_error is None:
            self.first_error = error

    def ready(self) -> bool:
        return self.first_error is not None or self.result is not None

    def error(self) -> Exception | None:
        assert self.ready()
        return self.first_error

    def value(self) -> Any:
        assert self.result is not None
        return self.result.value


@dataclass(slots=True)
class GatherFuture:
    """A future result of a dispatch.coroutine.gather() operation."""

    order: list[CoroutineID]
    waiting: set[CoroutineID]
    results: dict[CoroutineID, CoroutineResult]
    first_error: Exception | None = None

    def add_result(self, result: CallResult | CoroutineResult):
        assert isinstance(result, CoroutineResult)

        try:
            self.waiting.remove(result.coroutine_id)
        except KeyError:
            return

        if result.error is not None and self.first_error is None:
            self.first_error = result.error

        self.results[result.coroutine_id] = result

    def add_error(self, error: Exception):
        if self.first_error is not None:
            self.first_error = error

    def ready(self) -> bool:
        return self.first_error is not None or len(self.waiting) == 0

    def error(self) -> Exception | None:
        assert self.ready()
        return self.first_error

    def value(self) -> list[Any]:
        assert self.ready()
        assert len(self.waiting) == 0
        return [self.results[id].value for id in self.order]


@dataclass(slots=True)
class Coroutine:
    """An in-flight coroutine."""

    id: CoroutineID
    parent_id: CoroutineID | None
    coroutine: DurableCoroutine | DurableGenerator
    result: Future | None = None

    def run(self) -> Any:
        if self.result is None:
            return self.coroutine.send(None)
        assert self.result.ready()
        if (error := self.result.error()) is not None:
            return self.coroutine.throw(error)
        return self.coroutine.send(self.result.value())

    def __str__(self):
        return self.coroutine.__qualname__

    def __repr__(self):
        return f"Coroutine({self.id}, {self.coroutine.__qualname__})"


@dataclass(slots=True)
class State:
    """State of the scheduler and the coroutines it's managing."""

    version: str
    suspended: dict[CoroutineID, Coroutine]
    ready: list[Coroutine]
    next_coroutine_id: int
    next_call_id: int

    prev_callers: list[Coroutine]

    outstanding_calls: int


class OneShotScheduler:
    """Scheduler for local coroutines.

    It's a one-shot scheduler because it only runs one round of scheduling.
    When all local coroutines are suspended, the scheduler yields to Dispatch to
    take over scheduling asynchronous calls.
    """

    __slots__ = (
        "entry_point",
        "version",
        "poll_min_results",
        "poll_max_results",
        "poll_max_wait_seconds",
    )

    def __init__(
        self,
        entry_point: Callable,
        version: str = sys.version,
        poll_min_results: int = 1,
        poll_max_results: int = 10,
        poll_max_wait_seconds: int | None = None,
    ):
        """Initialize the scheduler.

        Args:
            entry_point: Entry point for the main coroutine.

            version: Version string to attach to scheduler/coroutine state.
                If the scheduler sees a version mismatch, it will respond to
                Dispatch with an INCOMPATIBLE_STATE status code.

            poll_min_results: Minimum number of call results to wait for before
                coroutine execution should continue. Dispatch waits until this
                many results are available, or the poll_max_wait_seconds
                timeout is reached, whichever comes first.

            poll_max_results: Maximum number of calls to receive from Dispatch
                per request.

            poll_max_wait_seconds: Maximum amount of time to suspend coroutines
                while waiting for call results. Optional.
        """
        self.entry_point = entry_point
        self.version = version
        self.poll_min_results = poll_min_results
        self.poll_max_results = poll_max_results
        self.poll_max_wait_seconds = poll_max_wait_seconds
        logger.debug(
            "booting coroutine scheduler with entry point '%s' version '%s'",
            entry_point.__qualname__,
            version,
        )

    def run(self, input: Input) -> Output:
        try:
            return self._run(input)
        except Exception as e:
            logger.exception(
                "unexpected exception occurred during coroutine scheduling"
            )
            return Output.error(Error.from_exception(e))

    def _init_state(self, input: Input) -> State:
        logger.debug("starting main coroutine")
        try:
            args, kwargs = input.input_arguments()
        except ValueError:
            raise ValueError("incorrect input for entry point")

        main = self.entry_point(*args, **kwargs)
        if not isinstance(main, DurableCoroutine):
            raise ValueError("entry point is not a @dispatch.function")

        return State(
            version=sys.version,
            suspended={},
            ready=[Coroutine(id=0, parent_id=None, coroutine=main)],
            next_coroutine_id=1,
            next_call_id=1,
            prev_callers=[],
            outstanding_calls=0,
        )

    def _rebuild_state(self, input: Input):
        logger.debug(
            "resuming scheduler with %d bytes of state", len(input.coroutine_state)
        )
        try:
            state = pickle.loads(input.coroutine_state)
            if not isinstance(state, State):
                raise ValueError("invalid state")
            if state.version != self.version:
                raise ValueError(
                    f"version mismatch: '{state.version}' vs. current '{self.version}'"
                )
            return state
        except (pickle.PickleError, ValueError) as e:
            logger.warning("state is incompatible", exc_info=True)
            raise IncompatibleStateError from e

    def _run(self, input: Input) -> Output:

        if input.is_first_call:
            state = self._init_state(input)
        else:
            state = self._rebuild_state(input)

            poll_error = input.poll_error
            if poll_error is not None:
                error = poll_error.to_exception()
                logger.debug("dispatching poll error: %s", error)
                for coroutine in state.prev_callers:
                    future = coroutine.result
                    assert future is not None
                    future.add_error(error)
                    if future.ready() and coroutine.id in state.suspended:
                        state.ready.append(coroutine)
                        del state.suspended[coroutine.id]
                        logger.debug("coroutine %s is now ready", coroutine)
                    state.outstanding_calls -= 1

            state.prev_callers = []

            logger.debug("dispatching %d call result(s)", len(input.call_results))
            for cr in input.call_results:
                assert cr.correlation_id is not None
                coroutine_id = correlation_coroutine_id(cr.correlation_id)
                call_id = correlation_call_id(cr.correlation_id)

                call_error = cr.error.to_exception() if cr.error is not None else None
                call_result = CallResult(
                    call_id=call_id, value=cr.output, error=call_error
                )

                try:
                    owner = state.suspended[coroutine_id]
                    future = owner.result
                    assert future is not None
                except (KeyError, AssertionError):
                    logger.warning("discarding unexpected call result %s", cr)
                    continue

                logger.debug("dispatching %s to %s", call_result, owner)
                future.add_result(call_result)
                if future.ready() and owner.id in state.suspended:
                    state.ready.append(owner)
                    del state.suspended[owner.id]
                    logger.debug("owner %s is now ready", owner)
                state.outstanding_calls -= 1

        logger.debug(
            "%d/%d coroutines are ready",
            len(state.ready),
            len(state.ready) + len(state.suspended),
        )

        pending_calls: list[Call] = []
        while state.ready:
            coroutine = state.ready.pop(0)
            logger.debug("running %s", coroutine)

            assert coroutine.id not in state.suspended

            coroutine_yield = None
            coroutine_result: CoroutineResult | None = None
            try:
                coroutine_yield = coroutine.run()
            except StopIteration as e:
                coroutine_result = CoroutineResult(
                    coroutine_id=coroutine.id, value=e.value
                )
            except Exception as e:
                logger.debug(
                    f"@dispatch.function: '{coroutine}' raised an exception", exc_info=e
                )
                coroutine_result = CoroutineResult(coroutine_id=coroutine.id, error=e)

            # Handle coroutines that return or raise.
            if coroutine_result is not None:
                if coroutine_result.error is not None:
                    logger.debug("%s raised %s", coroutine, coroutine_result.error)
                else:
                    logger.debug("%s returned %s", coroutine, coroutine_result.value)

                # If this is the main coroutine, we're done.
                if coroutine.parent_id is None:
                    for suspended in state.suspended.values():
                        suspended.coroutine.close()
                    if coroutine_result.error is not None:
                        return Output.error(
                            Error.from_exception(coroutine_result.error)
                        )
                    return Output.value(coroutine_result.value)

                # Otherwise, notify the parent of the result.
                try:
                    parent = state.suspended[coroutine.parent_id]
                    future = parent.result
                    assert future is not None
                except (KeyError, AssertionError):
                    logger.warning("discarding %s", coroutine_result)
                else:
                    future.add_result(coroutine_result)
                    if future.ready() and parent.id in state.suspended:
                        state.ready.insert(0, parent)
                        del state.suspended[parent.id]
                        logger.debug("parent %s is now ready", parent)
                continue

            # Handle coroutines that yield.
            logger.debug("%s yielded %s", coroutine, coroutine_yield)
            match coroutine_yield:
                case Call():
                    call = coroutine_yield
                    call_id = state.next_call_id
                    state.next_call_id += 1
                    call.correlation_id = correlation_id(coroutine.id, call_id)
                    logger.debug(
                        "enqueuing call %d (%s) for %s",
                        call_id,
                        call.function,
                        coroutine,
                    )
                    pending_calls.append(call)
                    coroutine.result = CallFuture()
                    state.suspended[coroutine.id] = coroutine
                    state.prev_callers.append(coroutine)
                    state.outstanding_calls += 1

                case Gather():
                    gather = coroutine_yield

                    children = []
                    for awaitable in gather.awaitables:
                        g = awaitable.__await__()
                        if not isinstance(g, DurableGenerator):
                            raise ValueError(
                                "gather awaitable is not a @dispatch.function"
                            )
                        child_id = state.next_coroutine_id
                        state.next_coroutine_id += 1
                        child = Coroutine(
                            id=child_id, parent_id=coroutine.id, coroutine=g
                        )
                        logger.debug("enqueuing %s for %s", child, coroutine)
                        children.append(child)

                    # Prepend children to get a depth-first traversal of coroutines.
                    state.ready = children + state.ready

                    child_ids = [child.id for child in children]
                    coroutine.result = GatherFuture(
                        order=child_ids, waiting=set(child_ids), results={}
                    )
                    state.suspended[coroutine.id] = coroutine

                case _:
                    raise RuntimeError(
                        f"coroutine unexpectedly yielded '{coroutine_yield}'"
                    )

        # Serialize coroutines and scheduler state.
        logger.debug("serializing state")
        try:
            serialized_state = pickle.dumps(state)
        except pickle.PickleError as e:
            logger.exception("state could not be serialized")
            return Output.error(Error.from_exception(e, status=Status.PERMANENT_ERROR))

        # Close coroutines before yielding.
        for suspended in state.suspended.values():
            suspended.coroutine.close()
        state.suspended = {}

        # Yield to Dispatch.
        logger.debug(
            "yielding to Dispatch with %d call(s) and %d bytes of state",
            len(pending_calls),
            len(serialized_state),
        )
        return Output.poll(
            state=serialized_state,
            calls=pending_calls,
            min_results=max(1, min(state.outstanding_calls, self.poll_min_results)),
            max_results=max(1, min(state.outstanding_calls, self.poll_max_results)),
            max_wait_seconds=self.poll_max_wait_seconds,
        )


def correlation_id(coroutine_id: CoroutineID, call_id: CallID) -> CorrelationID:
    return coroutine_id << 32 | call_id


def correlation_coroutine_id(correlation_id: CorrelationID) -> CoroutineID:
    return correlation_id >> 32


def correlation_call_id(correlation_id: CorrelationID) -> CallID:
    return correlation_id & 0xFFFFFFFF
