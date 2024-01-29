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

class Config(_message.Message):
    __slots__ = ("expire_at", "auto_discard", "scope", "signing_key_urn")
    EXPIRE_AT_FIELD_NUMBER: _ClassVar[int]
    AUTO_DISCARD_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    SIGNING_KEY_URN_FIELD_NUMBER: _ClassVar[int]
    expire_at: _timestamp_pb2.Timestamp
    auto_discard: bool
    scope: _containers.RepeatedCompositeFieldContainer[Scope]
    signing_key_urn: str
    def __init__(
        self,
        expire_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        auto_discard: bool = ...,
        scope: _Optional[_Iterable[_Union[Scope, _Mapping]]] = ...,
        signing_key_urn: _Optional[str] = ...,
    ) -> None: ...

class Scope(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(
        self, key: _Optional[str] = ..., value: _Optional[str] = ...
    ) -> None: ...
