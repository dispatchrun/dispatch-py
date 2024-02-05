from typing import ClassVar as _ClassVar
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import message as _message

from buf.validate import validate_pb2 as _validate_pb2
from dispatch.sdk.v1 import error_pb2 as _error_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class Call(_message.Message):
    __slots__ = ("correlation_id", "endpoint", "function", "input", "expiration")
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_FIELD_NUMBER: _ClassVar[int]
    correlation_id: int
    endpoint: str
    function: str
    input: _any_pb2.Any
    expiration: _duration_pb2.Duration
    def __init__(
        self,
        correlation_id: _Optional[int] = ...,
        endpoint: _Optional[str] = ...,
        function: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        expiration: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...,
    ) -> None: ...

class CallResult(_message.Message):
    __slots__ = ("correlation_id", "output", "error")
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    correlation_id: int
    output: _any_pb2.Any
    error: _error_pb2.Error
    def __init__(
        self,
        correlation_id: _Optional[int] = ...,
        output: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        error: _Optional[_Union[_error_pb2.Error, _Mapping]] = ...,
    ) -> None: ...
