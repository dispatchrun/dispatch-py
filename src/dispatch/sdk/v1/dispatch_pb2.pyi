from typing import ClassVar as _ClassVar
from typing import Iterable as _Iterable
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

from buf.validate import validate_pb2 as _validate_pb2
from dispatch.sdk.v1 import call_pb2 as _call_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class DispatchRequest(_message.Message):
    __slots__ = ("calls",)
    CALLS_FIELD_NUMBER: _ClassVar[int]
    calls: _containers.RepeatedCompositeFieldContainer[_call_pb2.Call]
    def __init__(
        self, calls: _Optional[_Iterable[_Union[_call_pb2.Call, _Mapping]]] = ...
    ) -> None: ...

class DispatchResponse(_message.Message):
    __slots__ = ("dispatch_ids",)
    DISPATCH_IDS_FIELD_NUMBER: _ClassVar[int]
    dispatch_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, dispatch_ids: _Optional[_Iterable[str]] = ...) -> None: ...
