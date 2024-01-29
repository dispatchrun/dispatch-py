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

class NetworkAccessControl(_message.Message):
    __slots__ = ("allow", "block")
    ALLOW_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    allow: _containers.RepeatedCompositeFieldContainer[NetworkPrefix]
    block: _containers.RepeatedCompositeFieldContainer[NetworkPrefix]
    def __init__(
        self,
        allow: _Optional[_Iterable[_Union[NetworkPrefix, _Mapping]]] = ...,
        block: _Optional[_Iterable[_Union[NetworkPrefix, _Mapping]]] = ...,
    ) -> None: ...

class NetworkPrefix(_message.Message):
    __slots__ = ("addr", "bits")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    BITS_FIELD_NUMBER: _ClassVar[int]
    addr: bytes
    bits: int
    def __init__(
        self, addr: _Optional[bytes] = ..., bits: _Optional[int] = ...
    ) -> None: ...
