"""Dispatch function interface.

Functions are currently created using the @app.dispatch_function() decorator
in a FastAPI app. See dispatch.fastapi for more details and examples.
"""

from __future__ import annotations

import enum
import pickle
from dataclasses import dataclass
from typing import Any, Callable

import google.protobuf.any_pb2
import google.protobuf.message
import google.protobuf.wrappers_pb2

from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import error_pb2 as error_pb
from dispatch.sdk.v1 import exit_pb2 as exit_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.sdk.v1 import poll_pb2 as poll_pb
from dispatch.sdk.v1 import status_pb2 as status_pb

# Most types in this package are thin wrappers around the various protobuf
# messages of dispatch.sdk.v1. They provide some safeguards and ergonomics.


@enum.unique
class Status(int, enum.Enum):
    """Enumeration of the possible values that can be used in the return status
    of functions.
    """

    UNSPECIFIED = status_pb.STATUS_UNSPECIFIED
    OK = status_pb.STATUS_OK
    TIMEOUT = status_pb.STATUS_TIMEOUT
    THROTTLED = status_pb.STATUS_THROTTLED
    INVALID_ARGUMENT = status_pb.STATUS_INVALID_ARGUMENT
    INVALID_RESPONSE = status_pb.STATUS_INVALID_RESPONSE
    TEMPORARY_ERROR = status_pb.STATUS_TEMPORARY_ERROR
    PERMANENT_ERROR = status_pb.STATUS_PERMANENT_ERROR
    INCOMPATIBLE_STATE = status_pb.STATUS_INCOMPATIBLE_STATE

    _proto: status_pb.Status


# Maybe we should find a better way to define that enum. It's that way to please
# Mypy and provide documentation for the enum values.

Status.UNSPECIFIED.__doc__ = "Status not specified (default)"
Status.UNSPECIFIED._proto = status_pb.STATUS_UNSPECIFIED
Status.OK.__doc__ = "Coroutine returned as expected"
Status.OK._proto = status_pb.STATUS_OK
Status.TIMEOUT.__doc__ = "Coroutine encountered a timeout and may be retried"
Status.TIMEOUT._proto = status_pb.STATUS_TIMEOUT
Status.THROTTLED.__doc__ = "Coroutine was throttled and may be retried later"
Status.THROTTLED._proto = status_pb.STATUS_THROTTLED
Status.INVALID_ARGUMENT.__doc__ = "Coroutine was provided an invalid type of input"
Status.INVALID_ARGUMENT._proto = status_pb.STATUS_INVALID_ARGUMENT
Status.INVALID_RESPONSE.__doc__ = "Coroutine was provided an unexpected reponse"
Status.INVALID_RESPONSE._proto = status_pb.STATUS_INVALID_RESPONSE
Status.TEMPORARY_ERROR.__doc__ = (
    "Coroutine encountered a temporary error, may be retried"
)
Status.TEMPORARY_ERROR._proto = status_pb.STATUS_TEMPORARY_ERROR
Status.PERMANENT_ERROR.__doc__ = (
    "Coroutine encountered a permanent error, should not be retried"
)
Status.PERMANENT_ERROR._proto = status_pb.STATUS_PERMANENT_ERROR
Status.INCOMPATIBLE_STATE.__doc__ = (
    "Coroutine was provided an incompatible state. May be restarted from scratch"
)
Status.INCOMPATIBLE_STATE._proto = status_pb.STATUS_INCOMPATIBLE_STATE


class Function:
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    def __init__(self, endpoint: str, name: str, func: Callable[[Input], Output]):
        self._endpoint = endpoint
        self._name = name
        self._func = func

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def name(self) -> str:
        return self._name

    def call_with(self, input: Any, correlation_id: int | None = None) -> Call:
        """Create a Call for this function with the provided input. Useful to
        generate calls when polling.

        Args:
            input: any pickle-able Python value that will be passed as input to
              this function.
            correlation_id: optional arbitrary integer the caller can use to
              match this call to a call result.

        Returns:
          A Call object. It can be passed to Output.poll().
        """
        return Call(
            correlation_id=correlation_id,
            endpoint=self.endpoint,
            function=self.name,
            input=input,
        )


class Input:
    """The input to a function.

    Functions always take a single argument of type Input. When the function is
    run for the first time, it receives the input. When the function is a coroutine
    that's resuming after a yield point, it receives the results of the yield
    directive. Use the is_first_call and is_resume properties to differentiate
    between the two cases.

    This class is intended to be used as read-only.
    """

    # TODO: first implementation with a single Input type, but we should
    # consider using some dynamic filling positional and keyword arguments.

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

    @property
    def coroutine_state(self) -> Any:
        self._assert_resume()
        return self._coroutine_state

    @property
    def call_results(self) -> Any:
        self._assert_resume()
        return self._call_results

    def _assert_first_call(self):
        if self.is_resume:
            raise ValueError("This input is for a resumed coroutine")

    def _assert_resume(self):
        if self.is_first_call:
            raise ValueError("This input is for a first function call")


class Output:
    """The output of a function.

    This class is meant to be instantiated and returned by authors of functions
    to indicate the follow up action they need to take. Use the various class
    methods create an instance of this class. For example Output.value() or
    Output.poll().
    """

    def __init__(self, proto: function_pb.RunResponse):
        self._message = proto

    @classmethod
    def value(cls, value: Any, status: Status = Status.OK) -> Output:
        """Terminally exit the function with the provided return value."""
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
    def poll(cls, state: Any, calls: None | list[Call] = None) -> Output:
        """Suspend the function with a set of Calls, instructing the
        orchestrator to resume the function with the provided state when
        call results are ready."""
        state_bytes = pickle.dumps(state)
        poll = poll_pb.Poll(coroutine_state=state_bytes)

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


@dataclass
class Call:
    """Instruction to call a function.

    Though this class can be built manually, it is recommended to use the
    with_call method of a Function instead.
    """

    function: str
    input: Any
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


@dataclass
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


class Error:
    """Error when running a function.

    This is not a Python exception, but potentially part of a CallResult or
    Output.
    """

    def __init__(self, status: Status, type: str | None, message: str | None):
        """Create a new Error.

        Args:
            status: categorization of the error.
            type: arbitrary string, used for humans. Optional.
            message: arbitrary message. Optional.

        Raises:
            ValueError: Neither type or message was provided or status is
              invalid.
        """
        if type is None and message is None:
            raise ValueError("At least one of type or message is required")
        if status is Status.OK:
            raise ValueError("Status cannot be OK")

        self.type = type
        self.message = message
        self.status = status

    @classmethod
    def from_exception(cls, ex: Exception, status: Status | None = None) -> Error:
        """Create an Error from a Python exception, using its class qualified
        named as type.

        The status tries to be inferred, but can be overriden. If it is not
        provided or cannot be inferred, it defaults to TEMPORARY_ERROR.
        """

        if status is None:
            status = Status.TEMPORARY_ERROR

        try:
            # Raise the exception and catch it so that the interpreter deals
            # with exception groups and chaining for us.
            raise ex
        except TimeoutError:
            status = Status.TIMEOUT
        except SyntaxError:
            status = Status.PERMANENT_ERROR
        except BaseException:
            pass
        # TODO: add more?

        return Error(status, ex.__class__.__qualname__, str(ex))

    @classmethod
    def _from_proto(cls, proto: error_pb.Error) -> Error:
        return cls(Status.UNSPECIFIED, proto.type, proto.message)

    def _as_proto(self) -> error_pb.Error:
        return error_pb.Error(type=self.type, message=self.message)


def _any_unpickle(any: google.protobuf.any_pb2.Any) -> Any:
    any.Unpack(value_bytes := google.protobuf.wrappers_pb2.BytesValue())
    return pickle.loads(value_bytes.value)


def _pb_any_pickle(x: Any) -> google.protobuf.any_pb2.Any:
    value_bytes = pickle.dumps(x)
    pb_bytes = google.protobuf.wrappers_pb2.BytesValue(value=value_bytes)
    pb_any = google.protobuf.any_pb2.Any()
    pb_any.Pack(pb_bytes)
    return pb_any
