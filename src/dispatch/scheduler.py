import logging
import pickle
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeAlias, cast

from dispatch.coroutine import Gather
from dispatch.error import IncompatibleStateError
from dispatch.experimental.durable.function import DurableCoroutine
from dispatch.proto import Call, CallResult, Error, Input, Output
from dispatch.status import Status

logger = logging.getLogger(__name__)


class OneShotScheduler:
    """Scheduler for local coroutines.

    It's a one-shot scheduler because it only runs one round of scheduling.
    When all local coroutines are suspended, the scheduler yields to Dispatch to
    take over scheduling asynchronous calls.
    """

    def __init__(self, entry_point: Callable[[Any], DurableCoroutine]):
        self.entry_point = entry_point
        logger.debug(
            f"booting coroutine scheduler with entry point '{entry_point.__qualname__}'"
        )

    def run(self, input: Input) -> Output:
        try:
            return self._run(input)
        except Exception as e:
            logger.exception(
                "unexpected exception occurred during coroutine scheduling"
            )
            return Output.error(Error.from_exception(e))

    def _run(self, input: Input) -> Output:
        state = self._prepare_state(input)

        # Run coroutines and accumulate calls until all coroutines have
        # yielded or the main coroutine returns.
        pending_calls: list[Call] = []
        while True:
            runnable = state.find_runnable()
            logger.debug(
                "%d/%d coroutine(s) are ready to run", len(runnable), len(state.waiting)
            )
            if not runnable:
                break

            for coro in runnable:
                throw, send = coro.prepare()

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
                # If this is the main coroutine, report the result back to
                # Dispatch. Otherwise, enqueue the result with the parent
                # coroutine.
                if result is not None:
                    if coro.id == _MAIN_COROUTINE_ID:
                        assert len(state.waiting) == 1
                        if result.error is not None:
                            return Output.error(Error.from_exception(result.error))
                        return Output.value(result.output)
                    else:
                        state.enqueue_coro_result(coro, result)
                        continue

                # Secondly, handle coroutines that yield.
                match directive:
                    case Call():
                        call_id = state.new_call_id()
                        directive.correlation_id = call_id
                        pending_calls.append(directive)
                        coro.waiting_on = ResultID(
                            result_type=ResultType.CALL, call_id=call_id
                        )
                        coro.waiting_calls = {call_id}
                        state.call_map[call_id] = coro.id
                        logger.debug(
                            "enqueuing call %d (%s)", call_id, directive.function
                        )

                    case Gather():
                        coro.waiting_on = []
                        for awaitable in directive.awaitables:
                            child_coro_id = state.new_coro_id()
                            child = InflightCoroutine(
                                id=child_coro_id,
                                coro=cast(DurableCoroutine, awaitable),
                            )
                            coro.waiting_on.append(
                                ResultID(
                                    result_type=ResultType.CORO, coro_id=child_coro_id
                                )
                            )
                            state.waiting[child_coro_id] = child
                            logger.debug("enqueuing coroutine %d", child_coro_id)
                            state.coro_map[child_coro_id] = coro.id
                            if coro.waiting_coros is None:
                                coro.waiting_coros = set()
                            coro.waiting_coros.add(child_coro_id)

                    case _:
                        raise RuntimeError(
                            f"coroutine unexpectedly yielded '{directive}'"
                        )

        logger.debug("serializing state")
        try:
            serialized_state = pickle.dumps(state)
        except pickle.PickleError as e:
            logger.exception("state could not be serialized")
            return Output.error(Error.from_exception(e, status=Status.PERMANENT_ERROR))

        logger.debug(
            "yielding to Dispatch with %d call(s) and %d bytes of state",
            len(pending_calls),
            len(serialized_state),
        )

        return Output.poll(
            state=serialized_state,
            calls=pending_calls,
            # FIXME: use min_results + max_results + max_wait to balance latency/throughput
            max_results=1,
        )

    def _prepare_state(self, input: Input) -> "State":
        """Create or deserialize the main coroutine and the scheduler's state."""
        if input.is_first_call:
            try:
                args, kwargs = input.input_arguments()
            except ValueError:
                raise ValueError("incorrect input for function")

            logger.debug("starting main coroutine")

            state = State.new(self.entry_point(*args, **kwargs))
            state.waiting[_MAIN_COROUTINE_ID] = InflightCoroutine(
                id=_MAIN_COROUTINE_ID, coro=state.main
            )

            return state

        logger.debug(
            "resuming with %d bytes of state and %d call result(s)",
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
            raise IncompatibleStateError from e

        state.enqueue_call_results(input.call_results)
        return state


_MAIN_COROUTINE_ID = 0


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
    result_type: ResultType
    call_id: CallID = -1
    coro_id: CoroID = -1


@dataclass
class InflightCoroutine:
    id: CoroID
    coro: DurableCoroutine

    waiting_on: list[ResultID] | ResultID | None = None

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

    def prepare(self) -> tuple[Exception | None, list[Any] | Any]:
        assert self.ready()

        throw: Exception | None = None
        send: list[Any] | Any = None

        if self.throw is not None:
            logger.debug(
                "preparing to resume coroutine %d (%s) with exception %s",
                self.id,
                self.name,
                self.throw,
            )
            throw = self.throw

        elif self.waiting_on is not None:
            calls = self.ready_calls if self.ready_calls is not None else {}
            coros = self.ready_coros if self.ready_coros is not None else {}
            if isinstance(self.waiting_on, list):
                send = []
                for result_id in self.waiting_on:
                    match result_id.result_type:
                        case ResultType.CALL:
                            send.append(calls[result_id.call_id].output)
                        case ResultType.CORO:
                            send.append(coros[result_id.coro_id].output)

                logger.debug(
                    "preparing to resume coroutine %d (%s) with %d result(s) ",
                    self.id,
                    self.name,
                    len(send),
                )
            else:
                result_id = self.waiting_on
                match result_id.result_type:
                    case ResultType.CALL:
                        send = calls[result_id.call_id].output
                    case ResultType.CORO:
                        send = coros[result_id.coro_id].output

                logger.debug(
                    "preparing to resume coroutine %d (%s) with result",
                    self.id,
                    self.name,
                )
        else:
            logger.debug("preparing to run coroutine %d (%s)", self.id, self.name)

        self.reset()
        return throw, send

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

    waiting: dict[CoroID, InflightCoroutine]
    call_map: dict[CallID, CoroID]
    coro_map: dict[CoroID, CoroID]

    next_coro_id: CoroID
    next_call_id: CallID

    @classmethod
    def new(cls, main: DurableCoroutine) -> "State":
        return State(
            main=main,
            version=sys.version,
            waiting={},
            call_map={},
            coro_map={},
            next_coro_id=_MAIN_COROUTINE_ID + 1,
            next_call_id=1,
        )

    def find_runnable(self) -> list[InflightCoroutine]:
        return [coro for coro in self.waiting.values() if coro.ready()]

    def enqueue_call_results(self, call_results: list[CallResult]):
        """Enqueue call results."""
        for call_result in call_results:
            call_id = cast(CallID, call_result.correlation_id)
            try:
                waiting_coro_id = self.call_map[call_id]
                waiting_coro = self.waiting[waiting_coro_id]
            except KeyError:
                logger.warning("skipping unexpected call result %s", call_result)
                continue
            else:
                del self.call_map[call_id]

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
                "queueing call result %d for coroutine %d (%s)",
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

    def enqueue_coro_result(self, coro: InflightCoroutine, result: CoroResult):
        """Enqueue the result of a coroutine."""
        assert coro.id in self.coro_map
        waiting_coro_id = self.coro_map[coro.id]
        del self.coro_map[coro.id]

        assert waiting_coro_id in self.waiting
        waiting_coro = self.waiting[waiting_coro_id]

        assert waiting_coro.waiting_coros is not None
        assert coro.id in waiting_coro.waiting_coros
        waiting_coro.waiting_coros.remove(coro.id)

        if waiting_coro.ready_coros is None:
            waiting_coro.ready_coros = {}
        waiting_coro.ready_coros[coro.id] = result
        if result.error is not None and waiting_coro.throw is None:
            waiting_coro.throw = result.error

        del self.waiting[coro.id]

    def new_coro_id(self) -> CoroID:
        coro_id = self.next_coro_id
        self.next_coro_id += 1
        return coro_id

    def new_call_id(self) -> CallID:
        call_id = self.next_call_id
        self.next_call_id += 1
        return call_id
