from ring.record.v1 import record_pb2 as _record_pb2
from ring.status.v1 import status_pb2 as _status_pb2
from ring.task.v1 import config_pb2 as _config_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class Submission(_message.Message):
    __slots__ = (
        "coroutine_uri",
        "input",
        "config",
        "time",
        "metadata",
        "coroutine_version",
        "task_id",
        "parent_task_id",
        "correlation_id",
    )
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    coroutine_uri: str
    input: _any_pb2.Any
    config: _config_pb2.Config
    time: _timestamp_pb2.Timestamp
    metadata: _any_pb2.Any
    coroutine_version: str
    task_id: _record_pb2.ID
    parent_task_id: _record_pb2.ID
    correlation_id: int
    def __init__(
        self,
        coroutine_uri: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        config: _Optional[_Union[_config_pb2.Config, _Mapping]] = ...,
        time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        metadata: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        coroutine_version: _Optional[str] = ...,
        task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        parent_task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        correlation_id: _Optional[int] = ...,
    ) -> None: ...

class Suspension(_message.Message):
    __slots__ = (
        "task_id",
        "state",
        "config",
        "time",
        "metadata",
        "coroutine_version",
        "correlation_id",
        "poll_deadline",
        "poll_max_results",
    )
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    POLL_DEADLINE_FIELD_NUMBER: _ClassVar[int]
    POLL_MAX_RESULTS_FIELD_NUMBER: _ClassVar[int]
    task_id: _record_pb2.ID
    state: bytes
    config: _config_pb2.Config
    time: _timestamp_pb2.Timestamp
    metadata: _any_pb2.Any
    coroutine_version: str
    correlation_id: int
    poll_deadline: _timestamp_pb2.Timestamp
    poll_max_results: int
    def __init__(
        self,
        task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        state: _Optional[bytes] = ...,
        config: _Optional[_Union[_config_pb2.Config, _Mapping]] = ...,
        time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        metadata: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        coroutine_version: _Optional[str] = ...,
        correlation_id: _Optional[int] = ...,
        poll_deadline: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        poll_max_results: _Optional[int] = ...,
    ) -> None: ...

class Completion(_message.Message):
    __slots__ = (
        "task_id",
        "error",
        "output",
        "time",
        "metadata",
        "coroutine_uri",
        "coroutine_version",
        "status",
        "correlation_id",
    )
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_VERSION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: _record_pb2.ID
    error: Error
    output: _any_pb2.Any
    time: _timestamp_pb2.Timestamp
    metadata: _any_pb2.Any
    coroutine_uri: str
    coroutine_version: str
    status: _status_pb2.Status
    correlation_id: int
    def __init__(
        self,
        task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        error: _Optional[_Union[Error, _Mapping]] = ...,
        output: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        metadata: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        coroutine_uri: _Optional[str] = ...,
        coroutine_version: _Optional[str] = ...,
        status: _Optional[_Union[_status_pb2.Status, str]] = ...,
        correlation_id: _Optional[int] = ...,
    ) -> None: ...

class Discard(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: _record_pb2.ID
    def __init__(
        self, task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...
    ) -> None: ...

class Error(_message.Message):
    __slots__ = ("message", "temporary", "timeout", "cancel")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TEMPORARY_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    message: str
    temporary: bool
    timeout: bool
    cancel: bool
    def __init__(
        self,
        message: _Optional[str] = ...,
        temporary: bool = ...,
        timeout: bool = ...,
        cancel: bool = ...,
    ) -> None: ...
