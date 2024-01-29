from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
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

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNSPECIFIED: _ClassVar[Status]
    STATUS_HEALTHY: _ClassVar[Status]
    STATUS_UNHEALTHY: _ClassVar[Status]

class PartitionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PARTITION_STATUS_UNSPECIFIED: _ClassVar[PartitionStatus]
    PARTITION_STATUS_ACTIVE: _ClassVar[PartitionStatus]
    PARTITION_STATUS_PASSIVE: _ClassVar[PartitionStatus]

STATUS_UNSPECIFIED: Status
STATUS_HEALTHY: Status
STATUS_UNHEALTHY: Status
PARTITION_STATUS_UNSPECIFIED: PartitionStatus
PARTITION_STATUS_ACTIVE: PartitionStatus
PARTITION_STATUS_PASSIVE: PartitionStatus

class InstanceDescription(_message.Message):
    __slots__ = (
        "id",
        "zone",
        "status",
        "port",
        "ipv4_addresses",
        "ipv6_addresses",
        "partitions",
        "ttl",
        "created_at",
        "updated_at",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    ZONE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    IPV4_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    IPV6_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    zone: str
    status: Status
    port: int
    ipv4_addresses: _containers.RepeatedScalarFieldContainer[str]
    ipv6_addresses: _containers.RepeatedScalarFieldContainer[str]
    partitions: _containers.RepeatedScalarFieldContainer[int]
    ttl: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(
        self,
        id: _Optional[str] = ...,
        zone: _Optional[str] = ...,
        status: _Optional[_Union[Status, str]] = ...,
        port: _Optional[int] = ...,
        ipv4_addresses: _Optional[_Iterable[str]] = ...,
        ipv6_addresses: _Optional[_Iterable[str]] = ...,
        partitions: _Optional[_Iterable[int]] = ...,
        ttl: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        updated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
    ) -> None: ...

class DescribeInstancesRequest(_message.Message):
    __slots__ = ("ids",)
    IDS_FIELD_NUMBER: _ClassVar[int]
    ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ids: _Optional[_Iterable[str]] = ...) -> None: ...

class DescribeInstancesResponse(_message.Message):
    __slots__ = ("instances",)
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    instances: _containers.RepeatedCompositeFieldContainer[InstanceDescription]
    def __init__(
        self,
        instances: _Optional[_Iterable[_Union[InstanceDescription, _Mapping]]] = ...,
    ) -> None: ...

class PartitionDescription(_message.Message):
    __slots__ = ("number", "owner", "creator", "created_at", "updated_at", "changelog")
    NUMBER_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    CREATOR_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    CHANGELOG_FIELD_NUMBER: _ClassVar[int]
    number: int
    owner: str
    creator: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    changelog: _containers.RepeatedCompositeFieldContainer[PartitionOwnershipChange]
    def __init__(
        self,
        number: _Optional[int] = ...,
        owner: _Optional[str] = ...,
        creator: _Optional[str] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        updated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        changelog: _Optional[
            _Iterable[_Union[PartitionOwnershipChange, _Mapping]]
        ] = ...,
    ) -> None: ...

class PartitionOwnershipChange(_message.Message):
    __slots__ = ("time", "owner")
    TIME_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    owner: str
    def __init__(
        self,
        time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        owner: _Optional[str] = ...,
    ) -> None: ...

class DescribePartitionsRequest(_message.Message):
    __slots__ = ("numbers",)
    NUMBERS_FIELD_NUMBER: _ClassVar[int]
    numbers: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, numbers: _Optional[_Iterable[int]] = ...) -> None: ...

class DescribePartitionsResponse(_message.Message):
    __slots__ = ("partitions",)
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    partitions: _containers.RepeatedCompositeFieldContainer[PartitionDescription]
    def __init__(
        self,
        partitions: _Optional[_Iterable[_Union[PartitionDescription, _Mapping]]] = ...,
    ) -> None: ...

class ZoneDescription(_message.Message):
    __slots__ = ("name", "instances", "partitions")
    NAME_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    name: str
    instances: _containers.RepeatedScalarFieldContainer[str]
    partitions: _containers.RepeatedScalarFieldContainer[int]
    def __init__(
        self,
        name: _Optional[str] = ...,
        instances: _Optional[_Iterable[str]] = ...,
        partitions: _Optional[_Iterable[int]] = ...,
    ) -> None: ...

class DescribeZonesRequest(_message.Message):
    __slots__ = ("names",)
    NAMES_FIELD_NUMBER: _ClassVar[int]
    names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, names: _Optional[_Iterable[str]] = ...) -> None: ...

class DescribeZonesResponse(_message.Message):
    __slots__ = ("zones",)
    ZONES_FIELD_NUMBER: _ClassVar[int]
    zones: _containers.RepeatedCompositeFieldContainer[ZoneDescription]
    def __init__(
        self, zones: _Optional[_Iterable[_Union[ZoneDescription, _Mapping]]] = ...
    ) -> None: ...

class InstanceSummary(_message.Message):
    __slots__ = (
        "instance",
        "zone",
        "status",
        "partitions",
        "ttl",
        "created_at",
        "updated_at",
    )
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    ZONE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    instance: str
    zone: str
    status: Status
    partitions: int
    ttl: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(
        self,
        instance: _Optional[str] = ...,
        zone: _Optional[str] = ...,
        status: _Optional[_Union[Status, str]] = ...,
        partitions: _Optional[int] = ...,
        ttl: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        updated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
    ) -> None: ...

class ListInstancesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListInstancesResponse(_message.Message):
    __slots__ = ("list",)
    LIST_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedCompositeFieldContainer[InstanceSummary]
    def __init__(
        self, list: _Optional[_Iterable[_Union[InstanceSummary, _Mapping]]] = ...
    ) -> None: ...

class PartitionOwnershipSummary(_message.Message):
    __slots__ = ("instance", "partitions")
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    instance: str
    partitions: _containers.RepeatedCompositeFieldContainer[PartitionSummary]
    def __init__(
        self,
        instance: _Optional[str] = ...,
        partitions: _Optional[_Iterable[_Union[PartitionSummary, _Mapping]]] = ...,
    ) -> None: ...

class PartitionSummary(_message.Message):
    __slots__ = ("partition", "created_at", "updated_at", "status")
    PARTITION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    partition: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    status: PartitionStatus
    def __init__(
        self,
        partition: _Optional[int] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        updated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        status: _Optional[_Union[PartitionStatus, str]] = ...,
    ) -> None: ...

class ListPartitionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListPartitionsResponse(_message.Message):
    __slots__ = ("list",)
    LIST_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedCompositeFieldContainer[PartitionOwnershipSummary]
    def __init__(
        self,
        list: _Optional[_Iterable[_Union[PartitionOwnershipSummary, _Mapping]]] = ...,
    ) -> None: ...

class ZoneSummary(_message.Message):
    __slots__ = ("zone", "instances", "partitions")
    ZONE_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    PARTITIONS_FIELD_NUMBER: _ClassVar[int]
    zone: str
    instances: int
    partitions: int
    def __init__(
        self,
        zone: _Optional[str] = ...,
        instances: _Optional[int] = ...,
        partitions: _Optional[int] = ...,
    ) -> None: ...

class ListZonesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListZonesResponse(_message.Message):
    __slots__ = ("list",)
    LIST_FIELD_NUMBER: _ClassVar[int]
    list: _containers.RepeatedCompositeFieldContainer[ZoneSummary]
    def __init__(
        self, list: _Optional[_Iterable[_Union[ZoneSummary, _Mapping]]] = ...
    ) -> None: ...
