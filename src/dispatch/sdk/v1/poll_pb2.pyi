from typing import ClassVar as _ClassVar
from typing import Iterable as _Iterable
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

from buf.validate import validate_pb2 as _validate_pb2
from dispatch.sdk.v1 import call_pb2 as _call_pb2
from dispatch.sdk.v1 import error_pb2 as _error_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class Poll(_message.Message):
    __slots__ = ("coroutine_state", "calls", "max_wait", "max_results", "min_results")
    COROUTINE_STATE_FIELD_NUMBER: _ClassVar[int]
    CALLS_FIELD_NUMBER: _ClassVar[int]
    MAX_WAIT_FIELD_NUMBER: _ClassVar[int]
    MAX_RESULTS_FIELD_NUMBER: _ClassVar[int]
    MIN_RESULTS_FIELD_NUMBER: _ClassVar[int]
    coroutine_state: bytes
    calls: _containers.RepeatedCompositeFieldContainer[_call_pb2.Call]
    max_wait: _duration_pb2.Duration
    max_results: int
    min_results: int
    def __init__(
        self,
        coroutine_state: _Optional[bytes] = ...,
        calls: _Optional[_Iterable[_Union[_call_pb2.Call, _Mapping]]] = ...,
        max_wait: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...,
        max_results: _Optional[int] = ...,
        min_results: _Optional[int] = ...,
    ) -> None: ...

class PollResult(_message.Message):
    __slots__ = ("coroutine_state", "results", "error")
    COROUTINE_STATE_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    coroutine_state: bytes
    results: _containers.RepeatedCompositeFieldContainer[_call_pb2.CallResult]
    error: _error_pb2.Error
    def __init__(
        self,
        coroutine_state: _Optional[bytes] = ...,
        results: _Optional[_Iterable[_Union[_call_pb2.CallResult, _Mapping]]] = ...,
        error: _Optional[_Union[_error_pb2.Error, _Mapping]] = ...,
    ) -> None: ...
