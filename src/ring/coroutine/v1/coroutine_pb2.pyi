from ring.status.v1 import status_pb2 as _status_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Iterable as _Iterable,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class ExecuteRequest(_message.Message):
    __slots__ = (
        "coroutine_uri",
        "coroutine_version",
        "input",
        "poll_response",
        "signing_key_urn",
    )
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    POLL_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    SIGNING_KEY_URN_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    coroutine_version: str
    input: _any_pb2.Any
    poll_response: PollResponse
    signing_key_urn: str
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        poll_response: _Optional[_Union[PollResponse, _Mapping]] = ...,
        signing_key_urn: _Optional[str] = ...,
    ) -> None: ...

class ExecuteResponse(_message.Message):
    __slots__ = ("coroutine_uri", "coroutine_version", "status", "exit", "poll")
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EXIT_FIELD_NUMBER: _ClassVar[int]
    POLL_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    coroutine_version: str
    status: _status_pb2.Status
    exit: Exit
    poll: Poll
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        status: _Optional[_Union[_status_pb2.Status, str]] = ...,
        exit: _Optional[_Union[Exit, _Mapping]] = ...,
        poll: _Optional[_Union[Poll, _Mapping]] = ...,
    ) -> None: ...

class Exit(_message.Message):
    __slots__ = ("result", "tail_call")
    RESULT_FIELD_NUMBER: _ClassVar[int]
    TAIL_CALL_FIELD_NUMBER: _ClassVar[int]
    result: Result
    tail_call: Call
    def __init__(
        self,
        result: _Optional[_Union[Result, _Mapping]] = ...,
        tail_call: _Optional[_Union[Call, _Mapping]] = ...,
    ) -> None: ...

class Result(_message.Message):
    __slots__ = ("output", "error")
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    output: _any_pb2.Any
    error: Error
    def __init__(
        self,
        output: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        error: _Optional[_Union[Error, _Mapping]] = ...,
    ) -> None: ...

class Error(_message.Message):
    __slots__ = ("type", "message")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    type: str
    message: str
    def __init__(
        self, type: _Optional[str] = ..., message: _Optional[str] = ...
    ) -> None: ...

class Poll(_message.Message):
    __slots__ = ("state", "calls", "max_wait", "max_results")
    STATE_FIELD_NUMBER: _ClassVar[int]
    CALLS_FIELD_NUMBER: _ClassVar[int]
    MAX_WAIT_FIELD_NUMBER: _ClassVar[int]
    MAX_RESULTS_FIELD_NUMBER: _ClassVar[int]
    state: bytes
    calls: _containers.RepeatedCompositeFieldContainer[Call]
    max_wait: _duration_pb2.Duration
    max_results: int
    def __init__(
        self,
        state: _Optional[bytes] = ...,
        calls: _Optional[_Iterable[_Union[Call, _Mapping]]] = ...,
        max_wait: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...,
        max_results: _Optional[int] = ...,
    ) -> None: ...

class PollResponse(_message.Message):
    __slots__ = ("state", "results")
    STATE_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    state: bytes
    results: _containers.RepeatedCompositeFieldContainer[CallResult]
    def __init__(
        self,
        state: _Optional[bytes] = ...,
        results: _Optional[_Iterable[_Union[CallResult, _Mapping]]] = ...,
    ) -> None: ...

class Call(_message.Message):
    __slots__ = ("coroutine_uri", "coroutine_version", "correlation_id", "input")
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    coroutine_version: str
    correlation_id: int
    input: _any_pb2.Any
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        correlation_id: _Optional[int] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
    ) -> None: ...

class CallResult(_message.Message):
    __slots__ = ("coroutine_uri", "coroutine_version", "correlation_id", "result")
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    coroutine_version: str
    correlation_id: int
    result: Result
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        correlation_id: _Optional[int] = ...,
        result: _Optional[_Union[Result, _Mapping]] = ...,
    ) -> None: ...
