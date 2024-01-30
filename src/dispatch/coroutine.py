"""Dispatch coroutine interface.

Coroutines are currently created using the @app.dispatch_coroutine() decorator
in a FastAPI app. See dispatch.fastapi for more details and examples. This
module describes how to write functions that get turned into coroutines.

Coroutines are functions that can yield at any point in their execution to save
progress and coordinate with other coroutines. They take exactly one argument of
type Input, and return an Output value.

"""

from __future__ import annotations
import enum
from typing import Any
from dataclasses import dataclass
import google.protobuf.message
import pickle
from ring.coroutine.v1 import coroutine_pb2
from ring.status.v1 import status_pb2


# Most types in this package are thin wrappers around the various protobuf
# messages of ring.coroutine.v1. They provide some safeguards and ergonomics.


@enum.unique
class Status(int, enum.Enum):
    """Enumeration of the possible values that can be used in the return status
    of couroutines.

    """

    UNSPECIFIED = status_pb2.STATUS_UNSPECIFIED
    OK = status_pb2.STATUS_OK
    TIMEOUT = status_pb2.STATUS_TIMEOUT
    THROTTLED = status_pb2.STATUS_THROTTLED
    INVALID_ARGUMENT = status_pb2.STATUS_INVALID_ARGUMENT
    INVALID_RESPONSE = status_pb2.STATUS_INVALID_RESPONSE
    TEMPORARY_ERROR = status_pb2.STATUS_TEMPORARY_ERROR
    PERMANENT_ERROR = status_pb2.STATUS_PERMANENT_ERROR
    INCOMPATIBLE_STATE = status_pb2.STATUS_INCOMPATIBLE_STATE

    _proto: status_pb2.Status


# Maybe we should find a better way to define that enum. It's that way to please
# Mypy and provide documentation for the enum values.

Status.UNSPECIFIED.__doc__ = "Status not specified (default)"
Status.UNSPECIFIED._proto = status_pb2.STATUS_UNSPECIFIED
Status.OK.__doc__ = "Coroutine returned as expected"
Status.OK._proto = status_pb2.STATUS_OK
Status.TIMEOUT.__doc__ = "Coroutine encountered a timeout and may be retried"
Status.TIMEOUT._proto = status_pb2.STATUS_TIMEOUT
Status.THROTTLED.__doc__ = "Coroutine was throttled and may be retried later"
Status.THROTTLED._proto = status_pb2.STATUS_THROTTLED
Status.INVALID_ARGUMENT.__doc__ = "Coroutine was provided an invalid type of input"
Status.INVALID_ARGUMENT._proto = status_pb2.STATUS_INVALID_ARGUMENT
Status.INVALID_RESPONSE.__doc__ = "Coroutine was provided an unexpected reponse"
Status.INVALID_RESPONSE._proto = status_pb2.STATUS_INVALID_RESPONSE
Status.TEMPORARY_ERROR.__doc__ = (
    "Coroutine encountered a temporary error, may be retried"
)
Status.TEMPORARY_ERROR._proto = status_pb2.STATUS_TEMPORARY_ERROR
Status.PERMANENT_ERROR.__doc__ = (
    "Coroutine encountered a permanent error, should not be retried"
)
Status.PERMANENT_ERROR._proto = status_pb2.STATUS_PERMANENT_ERROR
Status.INCOMPATIBLE_STATE.__doc__ = (
    "Coroutine was provided an incompatible state. May be restarted from scratch"
)
Status.INCOMPATIBLE_STATE._proto = status_pb2.STATUS_INCOMPATIBLE_STATE


class Coroutine:
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK."""

    def __init__(self, func):
        self._func = func

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    @property
    def uri(self) -> str:
        return self._func.__qualname__

    def call_with(self, input: Any, correlation_id: int | None = None) -> Call:
        """Create a Call of this coroutine with the provided input. Useful to
        generate calls during callbacks.

        Args:
            input: any pickle-able python value that will be passed as input to
              this coroutine.
            correlation_id: optional arbitrary integer the caller can use to
              match this call to a call result.

        Returns:
          A Call object. It can likely be passed to Output.callback().
        """
        return Call(
            coroutine_uri=self.uri,
            coroutine_version="v1",
            correlation_id=correlation_id,
            input=input,
        )


class Input:
    """The input to a coroutine.

    Coroutines always take a single argument of type Input. If the coroutine is
    started, it contains the input to the coroutine. If the coroutine is
    resumed, it contains the saved state and response to any poll requests. Use
    the is_first_call and is_resume properties to differentiate between the two
    cases.

    This class is intended to be used as read-only.

    """

    # TODO: first implementation with a single Input type, but we should
    # consider using some dynamic filling positional and keyword arguments.

    def __init__(self, req: coroutine_pb2.ExecuteRequest):
        self._has_input = req.HasField("input")
        if self._has_input:
            input_pb = google.protobuf.wrappers_pb2.BytesValue()
            req.input.Unpack(input_pb)
            input_bytes = input_pb.value
            if len(input_bytes) > 0:
                self._input = pickle.loads(input_bytes)
            else:
                self._input = None
        else:
            state_bytes = req.poll_response.state
            if len(state_bytes) > 0:
                self._state = pickle.loads(state_bytes)
            else:
                self._state = None
            self._calls = [CallResult(r) for r in req.poll_response.results]

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
    def state(self) -> Any:
        self._assert_resume()
        return self._state

    @property
    def calls(self) -> Any:
        self._assert_resume()
        return self._calls

    def _assert_first_call(self):
        if self.is_resume:
            raise ValueError("This input is for a resumed coroutine")

    def _assert_resume(self):
        if self.is_first_call:
            raise ValueError("This input is for a first coroutine call")


class Output:
    """The output of a coroutine.

    This class is meant to be instantiated and returned by authors of coroutines
    to indicate the follow up action they need to take. Use the various class
    methods create an instance of this class. For example Output.value() or
    Value.callback().

    """

    def __init__(self, proto: coroutine_pb2.ExecuteResponse):
        self._message = proto

    @classmethod
    def value(cls, value: Any, status: Status = Status.OK) -> Output:
        """Terminally exit the coroutine with the provided return value."""
        output_any = _pb_any_pickle(value)
        return Output(
            coroutine_pb2.ExecuteResponse(
                status=status._proto,
                exit=coroutine_pb2.Exit(result=coroutine_pb2.Result(output=output_any)),
            )
        )

    @classmethod
    def error(cls, error: Error) -> Output:
        """Terminally exit the coroutine with the provided error."""
        return Output(
            coroutine_pb2.ExecuteResponse(
                exit=coroutine_pb2.Exit(
                    result=coroutine_pb2.Result(error=error._as_proto())
                )
            )
        )

    @classmethod
    def callback(cls, state: Any, calls: None | list[Call] = None) -> Output:
        """Exit the coroutine instructing the orchestrator to call back this
        coroutine with the provided state. The state will be made available in
        Input.state."""
        state_bytes = pickle.dumps(state)
        poll = coroutine_pb2.Poll(state=state_bytes)

        if calls is not None:
            for c in calls:
                input_bytes = _pb_any_pickle(c.input)
                x = coroutine_pb2.Call(
                    coroutine_uri=c.coroutine_uri,
                    coroutine_version=c.coroutine_version,
                    correlation_id=c.correlation_id,
                    input=input_bytes,
                )
                poll.calls.append(x)

        return Output(coroutine_pb2.ExecuteResponse(poll=poll))


# Note: contrary to other classes here Call is not just a wrapper around its
# associated protobuf class, because it is reasonable for a human to write the
# Call manually -- for example to call a coroutine that cannot be referenced in
# the current Python process.


@dataclass
class Call:
    """Instruction to invoke a coroutine.

    Though this class can be built manually, it is recommended to use the
    with_call method of a Coroutine instead.

    """

    coroutine_uri: str
    coroutine_version: str
    correlation_id: int | None
    input: Any


class CallResult:
    """Result of a Call.

    Provided to a coroutine through its Input.calls value.

    This class is not meant to be instantiated directly.
    """

    def __init__(self, proto: coroutine_pb2.CallResult):
        self.coroutine_uri = proto.coroutine_uri
        self.coroutine_version = proto.coroutine_version
        self.correlation_id = proto.correlation_id
        self.result = None
        self.error = None
        if proto.result.HasField("output"):
            self.result = _any_unpickle(proto.result.output)
        else:
            self.error = Error._from_proto(proto.result.error)


class Error:
    """Error in the invocation of a coroutine.

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

    @classmethod
    def from_exception(cls, ex: Exception, status: Status | None = None) -> Error:
        """Create an Error from a Python exception, using its class qualified
        named as type.

        The status tries to be infied, but can be overriden. If it is not
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
    def _from_proto(cls, proto: coroutine_pb2.Error) -> Error:
        return cls(Status.UNSPECIFIED, proto.type, proto.message)

    def _as_proto(self) -> coroutine_pb2.Error:
        return coroutine_pb2.Error(type=self.type, message=self.message)


def _any_unpickle(any: google.protobuf.any_pb2.Any) -> Any:
    any.Unpack(value_bytes := google.protobuf.wrappers_pb2.BytesValue())
    return pickle.loads(value_bytes.value)


def _pb_any_pickle(x: Any) -> google.protobuf.any_pb2.Any:
    value_bytes = pickle.dumps(x)
    pb_bytes = google.protobuf.wrappers_pb2.BytesValue(value=value_bytes)
    pb_any = google.protobuf.any_pb2.Any()
    pb_any.Pack(pb_bytes)
    return pb_any


def _coroutine_uri_to_qualname(coroutine_uri: str) -> str:
    # TODO: fix this when we decide on the format of coroutine URIs.
    return coroutine_uri.split("/")[-1]
