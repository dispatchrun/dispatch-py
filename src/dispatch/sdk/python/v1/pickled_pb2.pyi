from typing import ClassVar as _ClassVar
from typing import Optional as _Optional

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class Pickled(_message.Message):
    __slots__ = ("pickled_value",)
    PICKLED_VALUE_FIELD_NUMBER: _ClassVar[int]
    pickled_value: bytes
    def __init__(self, pickled_value: _Optional[bytes] = ...) -> None: ...
