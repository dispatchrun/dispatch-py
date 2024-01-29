from ring.record.v1 import record_pb2 as _record_pb2
from ring.status.v1 import status_pb2 as _status_pb2
from ring.task.v1 import config_pb2 as _config_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
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

class Snapshot(_message.Message):
    __slots__ = ("tasks", "next_block_id")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    NEXT_BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[Task]
    next_block_id: int
    def __init__(
        self,
        tasks: _Optional[_Iterable[_Union[Task, _Mapping]]] = ...,
        next_block_id: _Optional[int] = ...,
    ) -> None: ...

class Task(_message.Message):
    __slots__ = (
        "submission_id",
        "suspension_id",
        "completion_id",
        "config",
        "flags",
        "coroutine_uri",
        "task_id",
        "status",
        "parent_task_id",
        "poll_deadline",
        "poll_max_results",
    )
    SUBMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    SUSPENSION_ID_FIELD_NUMBER: _ClassVar[int]
    COMPLETION_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    FLAGS_FIELD_NUMBER: _ClassVar[int]
    COROUTINE_URI_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PARENT_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    POLL_DEADLINE_FIELD_NUMBER: _ClassVar[int]
    POLL_MAX_RESULTS_FIELD_NUMBER: _ClassVar[int]
    submission_id: _record_pb2.ID
    suspension_id: _record_pb2.ID
    completion_id: _record_pb2.ID
    config: _config_pb2.Config
    flags: int
    coroutine_uri: str
    task_id: _record_pb2.ID
    status: _status_pb2.Status
    parent_task_id: _record_pb2.ID
    poll_deadline: _timestamp_pb2.Timestamp
    poll_max_results: int
    def __init__(
        self,
        submission_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        suspension_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        completion_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        config: _Optional[_Union[_config_pb2.Config, _Mapping]] = ...,
        flags: _Optional[int] = ...,
        coroutine_uri: _Optional[str] = ...,
        task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        status: _Optional[_Union[_status_pb2.Status, str]] = ...,
        parent_task_id: _Optional[_Union[_record_pb2.ID, _Mapping]] = ...,
        poll_deadline: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        poll_max_results: _Optional[int] = ...,
    ) -> None: ...
