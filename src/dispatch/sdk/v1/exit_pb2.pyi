from typing import ClassVar as _ClassVar
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

from buf.validate import validate_pb2 as _validate_pb2
from dispatch.sdk.v1 import call_pb2 as _call_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class Exit(_message.Message):
    __slots__ = ("result", "tail_call")
    RESULT_FIELD_NUMBER: _ClassVar[int]
    TAIL_CALL_FIELD_NUMBER: _ClassVar[int]
    result: _call_pb2.CallResult
    tail_call: _call_pb2.Call
    def __init__(
        self,
        result: _Optional[_Union[_call_pb2.CallResult, _Mapping]] = ...,
        tail_call: _Optional[_Union[_call_pb2.Call, _Mapping]] = ...,
    ) -> None: ...
