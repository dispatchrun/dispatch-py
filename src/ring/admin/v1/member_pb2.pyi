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

class MemberState(_message.Message):
    __slots__ = ("instances", "partitions")

    class Instance(_message.Message):
        __slots__ = ("id", "ttl")
        ID_FIELD_NUMBER: _ClassVar[int]
        TTL_FIELD_NUMBER: _ClassVar[int]
        id: str
        ttl: _timestamp_pb2.Timestamp
        def __init__(
            self,
            id: _Optional[str] = ...,
            ttl: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        ) -> None: ...

    class Partition(_message.Message):
        __slots__ = ("number", "owner", "creator")
        NUMBER_FIELD_NUMBER: _ClassVar[int]
        OWNER_FIELD_NUMBER: _ClassVar[int]
        CREATOR_FIELD_NUMBER: _ClassVar[int]
        number: int
        owner: str
        creator: str
        def __init__(
            self,
            number: _Optional[int] = ...,
            owner: _Optional[str] = ...,
            creator: _Optional[str] = ...,
        ) -> None: ...

    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    instances: _containers.RepeatedCompositeFieldContainer[MemberState.Instance]
    partitions: _containers.RepeatedCompositeFieldContainer[MemberState.Partition]
    def __init__(
        self,
        instances: _Optional[_Iterable[_Union[MemberState.Instance, _Mapping]]] = ...,
        partitions: _Optional[_Iterable[_Union[MemberState.Partition, _Mapping]]] = ...,
    ) -> None: ...

class MemberStateRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MemberStateResponse(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: MemberState
    def __init__(
        self, state: _Optional[_Union[MemberState, _Mapping]] = ...
    ) -> None: ...
