from typing import ClassVar as _ClassVar
from typing import Optional as _Optional

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class Error(_message.Message):
    __slots__ = ("type", "message", "value", "traceback")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    TRACEBACK_FIELD_NUMBER: _ClassVar[int]
    type: str
    message: str
    value: bytes
    traceback: bytes
    def __init__(
        self,
        type: _Optional[str] = ...,
        message: _Optional[str] = ...,
        value: _Optional[bytes] = ...,
        traceback: _Optional[bytes] = ...,
    ) -> None: ...
