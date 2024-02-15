import logging
import pickle
import sys
from dataclasses import dataclass
from enum import Enum
from queue import Queue
from types import coroutine
from typing import Any, Callable, TypeAlias, cast

from dispatch.experimental.durable import durable
from dispatch.experimental.durable.function import DurableCoroutine, DurableFunction
from dispatch.proto import Call, CallResult, Error, Input, Output
from dispatch.status import Status, status_for_output

logger = logging.getLogger(__name__)


@coroutine
@durable
def call(call: Call) -> Any:
    """Make an asynchronous function call and return its result. If the
    function call fails with an error, the error is raised."""
    return (yield call)


@dataclass
class Exit:
    result: Any | None
    tail_call: Call | None


@dataclass
class Poll:
    calls: list[Call]


CallID: TypeAlias = int
CoroID: TypeAlias = int


@dataclass
class CoroResult:
    output: Any | None = None
    error: Exception | None = None


class ResultType(Enum):
    CALL = 0
    CORO = 1


@dataclass
class ResultID:
    # TODO: improve this
    result_type: ResultType
    call_id: CallID = -1
    coro_id: CoroID = -1


@dataclass
class RunningCoro:
    id: CoroID
    coro: DurableCoroutine

    waiting_on: list[ResultID] | None = None

    waiting_calls: set[CallID] | None = None
    ready_calls: dict[CallID, CallResult] | None = None

    waiting_coros: set[CoroID] | None = None
    ready_coros: dict[CoroID, CoroResult] | None = None

    throw: Exception | None = None

    @property
    def name(self) -> str:
        return self.coro.__qualname__

    def ready(self) -> bool:
        if self.throw is not None:
            return True
        return not self.waiting_coros and not self.waiting_calls

    def reset(self):
        assert not self.waiting_calls and not self.waiting_coros

        self.throw = None
        self.ready_coros = None
        self.waiting_on = None
        self.waiting_coros = None
        self.waiting_calls = None
        self.ready_coros = None
        self.ready_calls = None


@dataclass
class State:
    main: DurableCoroutine
    version: str

    waiting: dict[CoroID, RunningCoro]
    call_map: dict[CallID, CoroID]
    coro_map: dict[CoroID, CoroID]

    next_coro_id: CoroID
    next_call_id: CallID


_MAIN_COROUTINE_ID = 0


def schedule(func: Callable[[Any], DurableCoroutine], input: Input) -> Output:
    """Schedule schedules a coroutine with the provided input."""
    try:
        call_results: list[CallResult] = []

        # Create or deserialize scheduler state.
        if input.is_first_call:
            logger.debug("starting scheduler")
            try:
                args, kwargs = input.input_arguments()
            except ValueError:
                raise ValueError("incorrect input for function")

            state = State(
                main=func(*args, **kwargs),
                version=sys.version,
                waiting={},
                call_map={},
                coro_map={},
                next_coro_id=0x1000,
                next_call_id=1,
            )

            main_coro = RunningCoro(id=_MAIN_COROUTINE_ID, coro=state.main)
            state.waiting[main_coro.id] = main_coro

        else:
            logger.debug(
                "resuming scheduler with %d bytes of state and %d call result(s)",
                len(input.coroutine_state),
                len(input.call_results),
            )
            try:
                state = pickle.loads(input.coroutine_state)
                if not isinstance(state, State):
                    raise ValueError("invalid state")
                if state.version != sys.version:
                    raise ValueError(
                        f"state version mismatch: '{state.version}' vs. current '{sys.version}'"
                    )
            except (pickle.PickleError, ValueError) as e:
                logger.warning("state is incompatible", exc_info=True)
                return Output.error(
                    Error.from_exception(e, status=Status.INCOMPATIBLE_STATE)
                )
            call_results = input.call_results

        # Dispatch call results.
        for call_result in call_results:
            call_id = cast(CallID, call_result.correlation_id)
            try:
                waiting_coro_id = state.call_map[call_id]
                waiting_coro = state.waiting[waiting_coro_id]
            except KeyError:
                logger.warning("skipping unexpected call result %s", call_result)
                continue
            else:
                del state.call_map[call_id]
            if (
                waiting_coro.waiting_calls is None
                or call_id not in waiting_coro.waiting_calls
            ):
                logger.warning(
                    "skipping unexpected call result %s for coroutine %d (%s)",
                    call_result,
                    waiting_coro.id,
                    waiting_coro.name,
                )
                continue

            logger.debug(
                "dispatching call %d to coroutine %d (%s)",
                call_id,
                waiting_coro.id,
                waiting_coro.name,
            )
            if waiting_coro.ready_calls is None:
                waiting_coro.ready_calls = {}
            waiting_coro.ready_calls[call_id] = call_result
            waiting_coro.waiting_calls.remove(call_id)
            if call_result.error is not None and waiting_coro.throw is None:
                waiting_coro.throw = call_result.error.to_exception()

        pending_calls: list[Call] = []

        # Run until there's no more work to do.
        while True:
            # Find coroutines that are ready to run now.
            pending: list[RunningCoro] = []
            for coro in state.waiting.values():
                if coro.ready():
                    pending.append(coro)
            logger.debug(
                "%d/%d coroutine(s) are ready to run", len(pending), len(state.waiting)
            )
            if not pending:
                break

            while pending:
                coro = pending.pop(0)

                # Determine what to send or throw to the coroutine.
                throw = None
                send = None
                if coro.throw is not None:
                    throw = coro.throw
                    logger.debug(
                        "throwing exception %s in coroutine %d (%s)",
                        throw,
                        coro.id,
                        coro.name,
                    )
                elif coro.waiting_on is not None:
                    send = []
                    ready_calls = (
                        coro.ready_calls if coro.ready_calls is not None else {}
                    )
                    ready_coros = (
                        coro.ready_coros if coro.ready_coros is not None else {}
                    )
                    for result_id in coro.waiting_on:
                        match result_id.result_type:
                            case ResultType.CALL:
                                send.append(ready_calls[result_id.call_id].output)
                            case ResultType.CORO:
                                send.append(ready_coros[result_id.coro_id].output)
                    logger.debug(
                        "sending %d result(s) to coroutine %d (%s)",
                        len(send),
                        coro.id,
                        coro.name,
                    )
                else:
                    logger.debug("running coroutine %d (%s)", coro.id, coro.name)

                coro.reset()

                # Run the coroutine until it yields, returns or raises an error.
                directive = None
                result: CoroResult | None = None
                try:
                    if throw is not None:
                        directive = coro.coro.throw(throw)
                    else:
                        directive = coro.coro.send(send)
                except StopIteration as e:
                    result = CoroResult(output=e.value)
                except Exception as e:
                    result = CoroResult(error=e)

                # Firstly, handle coroutines that return or raise an error.
                # If this is the main coroutine, report the result back to the orchestrator.
                # Otherwise, dispatch the result to the parent coroutine.
                if result is not None:
                    if coro.id == _MAIN_COROUTINE_ID:
                        assert len(state.waiting) == 1
                        if result.error is not None:
                            return Output.error(Error.from_exception(result.error))
                        return Output.value(result.output)

                    assert coro.id in state.coro_map
                    waiting_coro_id = state.coro_map[coro.id]
                    del state.coro_map[coro.id]

                    assert waiting_coro_id in state.waiting
                    waiting_coro = state.waiting[waiting_coro_id]

                    assert waiting_coro.waiting_coros is not None
                    assert coro.id in waiting_coro.waiting_coros
                    waiting_coro.waiting_coros.remove(coro.id)

                    if waiting_coro.ready_coros is None:
                        waiting_coro.ready_coros = {}
                    waiting_coro.ready_coros[coro.id] = result
                    if result.error is not None and waiting_coro.throw is None:
                        waiting_coro.throw = result.error

                    del state.waiting[coro.id]
                    continue

                # Secondly, handle coroutines that yield.
                match directive:
                    case Call():
                        call_id = state.next_call_id
                        state.next_call_id += 1
                        coro.waiting_on = [
                            ResultID(result_type=ResultType.CALL, call_id=call_id)
                        ]
                        coro.waiting_calls = {call_id}
                        directive.correlation_id = call_id
                        pending_calls.append(directive)
                        state.call_map[call_id] = coro.id
                        logger.debug(
                            "queuing call %d (%s)", call_id, directive.function
                        )
                    case _:
                        raise RuntimeError(
                            f"coroutine unexpectedly yielded '{directive}'"
                        )

        try:
            serialized_state = pickle.dumps(state)
        except pickle.PickleError as e:
            logger.exception("state could not be serialized")
            return Output.error(Error.from_exception(e, status=Status.PERMANENT_ERROR))

        return Output.poll(state=serialized_state, calls=pending_calls)

    except Exception as e:
        logger.exception(f"@dispatch.coroutine: '{func.__name__}' raised an exception")
        return Output.error(Error.from_exception(e))
