from ring.record.v1 import record_pb2 as _record_pb2
from ring.task.v1 import config_pb2 as _config_pb2
from google.protobuf import any_pb2 as _any_pb2
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

class CreateTaskInput(_message.Message):
    __slots__ = ("coroutine_uri", "input", "config", "metadata")
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    input: _any_pb2.Any
    config: _config_pb2.Config
    metadata: _any_pb2.Any
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        config: _Optional[_Union[_config_pb2.Config, _Mapping]] = ...,
        metadata: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
    ) -> None: ...

class CreateTaskOutput(_message.Message):
    __slots__ = ("config", "id")
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    config: _config_pb2.Config
    id: _record_pb2.ID
    def __init__(
        self,
        config: _Optional[_Union[_config_pb2.Config, _Mapping]] = ...,
        id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
    ) -> None: ...

class CreateTasksRequest(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[CreateTaskInput]
    def __init__(
        self, tasks: _Optional[_Iterable[_Union[CreateTaskInput, _Mapping]]] = ...
    ) -> None: ...

class CreateTasksResponse(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[CreateTaskOutput]
    def __init__(
        self, tasks: _Optional[_Iterable[_Union[CreateTaskOutput, _Mapping]]] = ...
    ) -> None: ...
