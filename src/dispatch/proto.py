from __future__ import annotations

import pickle
from dataclasses import dataclass
from traceback import format_exception
from types import TracebackType
from typing import Any

import google.protobuf.any_pb2
import google.protobuf.message
import google.protobuf.wrappers_pb2
import tblib  # type: ignore[import-untyped]
from google.protobuf import duration_pb2

from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import error_pb2 as error_pb
from dispatch.sdk.v1 import exit_pb2 as exit_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.sdk.v1 import poll_pb2 as poll_pb
from dispatch.sdk.v1 import status_pb2 as status_pb
from dispatch.status import Status, status_for_error, status_for_output

# Most types in this package are thin wrappers around the various protobuf
# messages of dispatch.sdk.v1. They provide some safeguards and ergonomics.


class Input:
    """The input to a primitive function.

    Functions always take a single argument of type Input. When the function is
    run for the first time, it receives the input. When the function is a coroutine
    that's resuming after a yield point, it receives the results of the yield
    directive. Use the is_first_call and is_resume properties to differentiate
    between the two cases.

    This class is intended to be used as read-only.
    """

    __slots__ = (
        "_has_input",
        "_input",
        "_coroutine_state",
        "_call_results",
        "_poll_error",
    )

    def __init__(self, req: function_pb.RunRequest):
        self._has_input = req.HasField("input")
        if self._has_input:
            input_pb = google.protobuf.wrappers_pb2.BytesValue()
            req.input.Unpack(input_pb)
            input_bytes = input_pb.value
            self._input = pickle.loads(input_bytes)
        else:
            state_bytes = req.poll_result.coroutine_state
            if len(state_bytes) > 0:
                self._coroutine_state = pickle.loads(state_bytes)
            else:
                self._coroutine_state = None
            self._call_results = [
                CallResult._from_proto(r) for r in req.poll_result.results
            ]
            self._poll_error = (
                Error._from_proto(req.poll_result.error)
                if req.poll_result.HasField("error")
                else None
            )

    @property
    def is_first_call(self) -> bool:
        return self._has_input

    @property
    def is_resume(self) -> bool:
        return not self.is_first_call

    @property
    def input(self) -> Any:
        self._assert_first_call()
        return self._input

    def input_arguments(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Returns positional and keyword arguments carried by the input."""
        self._assert_first_call()
        if not isinstance(self._input, Arguments):
            raise RuntimeError("input does not hold arguments")
        return self._input.args, self._input.kwargs

    @property
    def coroutine_state(self) -> Any:
        self._assert_resume()
        return self._coroutine_state

    @property
    def call_results(self) -> list[CallResult]:
        self._assert_resume()
        return self._call_results

    @property
    def poll_error(self) -> Error | None:
        self._assert_resume()
        return self._poll_error

    def _assert_first_call(self):
        if self.is_resume:
            raise ValueError("This input is for a resumed coroutine")

    def _assert_resume(self):
        if self.is_first_call:
            raise ValueError("This input is for a first function call")

    @classmethod
    def from_input_arguments(cls, function: str, *args, **kwargs):
        input = Arguments(args=args, kwargs=kwargs)
        return Input(
            req=function_pb.RunRequest(
                function=function,
                input=_pb_any_pickle(input),
            )
        )

    @classmethod
    def from_poll_results(
        cls,
        function: str,
        coroutine_state: Any,
        call_results: list[CallResult],
        error: Error | None = None,
    ):
        return Input(
            req=function_pb.RunRequest(
                function=function,
                poll_result=poll_pb.PollResult(
                    coroutine_state=coroutine_state,
                    results=[result._as_proto() for result in call_results],
                    error=error._as_proto() if error else None,
                ),
            )
        )


@dataclass(slots=True)
class Arguments:
    """A container for positional and keyword arguments."""

    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass(slots=True)
class Output:
    """The output of a primitive function.

    This class is meant to be instantiated and returned by authors of functions
    to indicate the follow up action they need to take. Use the various class
    methods create an instance of this class. For example Output.value() or
    Output.poll().
    """

    _message: function_pb.RunResponse

    def __init__(self, proto: function_pb.RunResponse):
        self._message = proto

    @classmethod
    def value(cls, value: Any, status: Status | None = None) -> Output:
        """Terminally exit the function with the provided return value."""
        if status is None:
            status = status_for_output(value)
        return cls.exit(result=CallResult.from_value(value), status=status)

    @classmethod
    def error(cls, error: Error) -> Output:
        """Terminally exit the function with the provided error."""
        return cls.exit(result=CallResult.from_error(error), status=error.status)

    @classmethod
    def tail_call(cls, tail_call: Call) -> Output:
        """Terminally exit the function, and instruct the orchestrator to
        tail call the specified function."""
        return cls.exit(tail_call=tail_call)

    @classmethod
    def exit(
        cls,
        result: CallResult | None = None,
        tail_call: Call | None = None,
        status: Status = Status.OK,
    ) -> Output:
        """Terminally exit the function."""
        result_proto = result._as_proto() if result else None
        tail_call_proto = tail_call._as_proto() if tail_call else None
        return Output(
            function_pb.RunResponse(
                status=status._proto,
                exit=exit_pb.Exit(result=result_proto, tail_call=tail_call_proto),
            )
        )

    @classmethod
    def poll(
        cls,
        state: Any,
        calls: None | list[Call] = None,
        min_results: int = 1,
        max_results: int = 10,
        max_wait_seconds: int | None = None,
    ) -> Output:
        """Suspend the function with a set of Calls, instructing the
        orchestrator to resume the function with the provided state when
        call results are ready."""
        state_bytes = pickle.dumps(state)
        max_wait = (
            duration_pb2.Duration(seconds=max_wait_seconds)
            if max_wait_seconds is not None
            else None
        )
        poll = poll_pb.Poll(
            coroutine_state=state_bytes,
            min_results=min_results,
            max_results=max_results,
            max_wait=max_wait,
        )

        if calls is not None:
            for c in calls:
                poll.calls.append(c._as_proto())

        return Output(
            function_pb.RunResponse(
                status=status_pb.STATUS_OK,
                poll=poll,
            )
        )


# Note: contrary to other classes here Call is not just a wrapper around its
# associated protobuf class, because it is reasonable for a human to write the
# Call manually -- for example to call a function that cannot be referenced in
# the current Python process.


@dataclass(slots=True)
class Call:
    """Instruction to call a function.

    Though this class can be built manually, it is recommended to use the
    with_call method of a Function instead.
    """

    function: str
    input: Any | None = None
    endpoint: str | None = None
    correlation_id: int | None = None

    def _as_proto(self) -> call_pb.Call:
        input_bytes = _pb_any_pickle(self.input)
        return call_pb.Call(
            correlation_id=self.correlation_id,
            endpoint=self.endpoint,
            function=self.function,
            input=input_bytes,
        )


@dataclass(slots=True)
class CallResult:
    """Result of a Call."""

    correlation_id: int | None = None
    output: Any | None = None
    error: Error | None = None

    def _as_proto(self) -> call_pb.CallResult:
        output_any = None
        error_proto = None
        if self.output is not None:
            output_any = _pb_any_pickle(self.output)
        if self.error is not None:
            error_proto = self.error._as_proto()

        return call_pb.CallResult(
            correlation_id=self.correlation_id, output=output_any, error=error_proto
        )

    @classmethod
    def _from_proto(cls, proto: call_pb.CallResult) -> CallResult:
        output = None
        error = None
        if proto.HasField("output"):
            output = _any_unpickle(proto.output)
        if proto.HasField("error"):
            error = Error._from_proto(proto.error)

        return CallResult(
            correlation_id=proto.correlation_id, output=output, error=error
        )

    @classmethod
    def from_value(cls, output: Any, correlation_id: int | None = None) -> CallResult:
        return CallResult(correlation_id=correlation_id, output=output)

    @classmethod
    def from_error(cls, error: Error, correlation_id: int | None = None) -> CallResult:
        return CallResult(correlation_id=correlation_id, error=error)


@dataclass(slots=True)
class Error:
    """Error when running a function.

    This is not a Python exception, but potentially part of a CallResult or
    Output.
    """

    status: Status
    type: str
    message: str
    value: Exception | None = None
    traceback: bytes | None = None

    def __init__(
        self,
        status: Status,
        type: str,
        message: str,
        value: Exception | None = None,
        traceback: bytes | None = None,
    ):
        """Create a new Error.

        Args:
            status: categorization of the error.
            type: arbitrary string, used for humans.
            message: arbitrary message.
            value: arbitrary exception from which the error is derived. Optional.

        Raises:
            ValueError: Neither type or message was provided or status is
                invalid.
        """
        if type is None:
            raise ValueError("Error type is required")
        if message is None:
            raise ValueError("Error message is required")
        if status is Status.OK:
            raise ValueError("Status cannot be OK")

        self.type = type
        self.message = message
        self.status = status
        self.value = value
        self.traceback = traceback
        if not traceback and value:
            self.traceback = "".join(format_exception(value)).encode("utf-8")

    @classmethod
    def from_exception(cls, ex: Exception, status: Status | None = None) -> Error:
        """Create an Error from a Python exception, using its class qualified
        named as type.

        The status tries to be inferred, but can be overridden. If it is not
        provided or cannot be inferred, it defaults to TEMPORARY_ERROR.
        """
        if status is None:
            status = status_for_error(ex)
        return Error(status, ex.__class__.__qualname__, str(ex), ex)

    def to_exception(self) -> Exception:
        """Returns an equivalent exception."""
        if self.value is not None:
            e = self.value
        else:
            g = globals()
            try:
                assert isinstance(self.type, str)
                cls = g[self.type]
                assert issubclass(cls, Exception)
            except (KeyError, AssertionError):
                e = RuntimeError(self.message)
            else:
                e = cls(self.message)
        if self.traceback is not None:
            try:
                t = self.traceback.decode("utf-8")
                e.__traceback__ = tblib.Traceback.from_string(t).as_traceback()
            except Exception:
                pass  # ignore, better to not have a traceback than to crash
        return e

    @classmethod
    def _from_proto(cls, proto: error_pb.Error) -> Error:
        value = pickle.loads(proto.value) if proto.value else None
        return cls(
            Status.UNSPECIFIED, proto.type, proto.message, value, proto.traceback
        )

    def _as_proto(self) -> error_pb.Error:
        value = pickle.dumps(self.value) if self.value else None
        return error_pb.Error(
            type=self.type, message=self.message, value=value, traceback=self.traceback
        )


def _any_unpickle(any: google.protobuf.any_pb2.Any) -> Any:
    any.Unpack(value_bytes := google.protobuf.wrappers_pb2.BytesValue())
    return pickle.loads(value_bytes.value)


def _pb_any_pickle(x: Any) -> google.protobuf.any_pb2.Any:
    value_bytes = pickle.dumps(x)
    pb_bytes = google.protobuf.wrappers_pb2.BytesValue(value=value_bytes)
    pb_any = google.protobuf.any_pb2.Any()
    pb_any.Pack(pb_bytes)
    return pb_any
