from typing import ClassVar as _ClassVar
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import timestamp_pb2 as _timestamp_pb2

from dispatch.sdk.v1 import exit_pb2 as _exit_pb2
from dispatch.sdk.v1 import poll_pb2 as _poll_pb2
from dispatch.sdk.v1 import status_pb2 as _status_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class RunRequest(_message.Message):
    __slots__ = (
        "function",
        "input",
        "poll_result",
        "dispatch_id",
        "parent_dispatch_id",
        "root_dispatch_id",
        "creation_time",
        "expiration_time",
    )
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    POLL_RESULT_FIELD_NUMBER: _ClassVar[int]
    DISPATCH_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_DISPATCH_ID_FIELD_NUMBER: _ClassVar[int]
    ROOT_DISPATCH_ID_FIELD_NUMBER: _ClassVar[int]
    CREATION_TIME_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_TIME_FIELD_NUMBER: _ClassVar[int]
    function: str
    input: _any_pb2.Any
    poll_result: _poll_pb2.PollResult
    dispatch_id: str
    parent_dispatch_id: str
    root_dispatch_id: str
    creation_time: _timestamp_pb2.Timestamp
    expiration_time: _timestamp_pb2.Timestamp
    def __init__(
        self,
        function: _Optional[str] = ...,
        input: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        poll_result: _Optional[_Union[_poll_pb2.PollResult, _Mapping]] = ...,
        dispatch_id: _Optional[str] = ...,
        parent_dispatch_id: _Optional[str] = ...,
        root_dispatch_id: _Optional[str] = ...,
        creation_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        expiration_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
    ) -> None: ...

class RunResponse(_message.Message):
    __slots__ = ("status", "exit", "poll")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EXIT_FIELD_NUMBER: _ClassVar[int]
    POLL_FIELD_NUMBER: _ClassVar[int]
    status: _status_pb2.Status
    exit: _exit_pb2.Exit
    poll: _poll_pb2.Poll
    def __init__(
        self,
        status: _Optional[_Union[_status_pb2.Status, str]] = ...,
        exit: _Optional[_Union[_exit_pb2.Exit, _Mapping]] = ...,
        poll: _Optional[_Union[_poll_pb2.Poll, _Mapping]] = ...,
    ) -> None: ...
