from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Metadata(_message.Message):
    __slots__ = ("organization_id", "key_id")
    ORGANIZATION_ID_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    organization_id: int
    key_id: int
    def __init__(
        self, organization_id: _Optional[int] = ..., key_id: _Optional[int] = ...
    ) -> None: ...
