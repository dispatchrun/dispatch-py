from typing import ClassVar as _ClassVar
from typing import Iterable as _Iterable
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class CreateExecutionsRequest(_message.Message):
    __slots__ = ("executions",)
    EXECUTIONS_FIELD_NUMBER: _ClassVar[int]
    executions: _containers.RepeatedCompositeFieldContainer[Execution]
    def __init__(
        self, executions: _Optional[_Iterable[_Union[Execution, _Mapping]]] = ...
    ) -> None: ...

class CreateExecutionsResponse(_message.Message):
    __slots__ = ("ids",)
    IDS_FIELD_NUMBER: _ClassVar[int]
    ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ids: _Optional[_Iterable[str]] = ...) -> None: ...

class Execution(_message.Message):
    __slots__ = ("coroutine_uri", "coroutine_version", "input", "expiration")
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    coroutine_version: str
    input: _any_pb2.Any
    expiration: _duration_pb2.Duration
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        expiration: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...,
    ) -> None: ...
