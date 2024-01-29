from google.protobuf import any_pb2 as _any_pb2
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

class Block(_message.Message):
    __slots__ = ("records",)
    RECORDS_FIELD_NUMBER: _ClassVar[int]
    records: _containers.RepeatedCompositeFieldContainer[Record]
    def __init__(
        self, records: _Optional[_Iterable[_Union[Record, _Mapping]]] = ...
    ) -> None: ...

class Record(_message.Message):
    __slots__ = ("message", "crc32_checksum", "flags")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CRC32_CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    FLAGS_FIELD_NUMBER: _ClassVar[int]
    message: _any_pb2.Any
    crc32_checksum: int
    flags: int
    def __init__(
        self,
        message: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        crc32_checksum: _Optional[int] = ...,
        flags: _Optional[int] = ...,
    ) -> None: ...

class ID(_message.Message):
    __slots__ = ("partition_number", "block_id", "record_offset", "record_size")
    PARTITION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    RECORD_OFFSET_FIELD_NUMBER: _ClassVar[int]
    RECORD_SIZE_FIELD_NUMBER: _ClassVar[int]
    partition_number: int
    block_id: int
    record_offset: int
    record_size: int
    def __init__(
        self,
        partition_number: _Optional[int] = ...,
        block_id: _Optional[int] = ...,
        record_offset: _Optional[int] = ...,
        record_size: _Optional[int] = ...,
    ) -> None: ...

class Prefix(_message.Message):
    __slots__ = ("partition_number", "block_id")
    PARTITION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    partition_number: int
    block_id: int
    def __init__(
        self, partition_number: _Optional[int] = ..., block_id: _Optional[int] = ...
    ) -> None: ...

class Range(_message.Message):
    __slots__ = (
        "partition_number",
        "block_id",
        "range_offset",
        "range_size",
        "full_block",
    )
    PARTITION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    RANGE_OFFSET_FIELD_NUMBER: _ClassVar[int]
    RANGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    FULL_BLOCK_FIELD_NUMBER: _ClassVar[int]
    partition_number: int
    block_id: int
    range_offset: int
    range_size: int
    full_block: bool
    def __init__(
        self,
        partition_number: _Optional[int] = ...,
        block_id: _Optional[int] = ...,
        range_offset: _Optional[int] = ...,
        range_size: _Optional[int] = ...,
        full_block: bool = ...,
    ) -> None: ...

class Error(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class BlockTriggerRecord(_message.Message):
    __slots__ = ("message", "record_offset", "record_size")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RECORD_OFFSET_FIELD_NUMBER: _ClassVar[int]
    RECORD_SIZE_FIELD_NUMBER: _ClassVar[int]
    message: _any_pb2.Any
    record_offset: int
    record_size: int
    def __init__(
        self,
        message: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...,
        record_offset: _Optional[int] = ...,
        record_size: _Optional[int] = ...,
    ) -> None: ...

class BlockTriggerRequest(_message.Message):
    __slots__ = ("prefix", "records")
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    RECORDS_FIELD_NUMBER: _ClassVar[int]
    prefix: Prefix
    records: _containers.RepeatedCompositeFieldContainer[BlockTriggerRecord]
    def __init__(
        self,
        prefix: _Optional[_Union[Prefix, _Mapping]] = ...,
        records: _Optional[_Iterable[_Union[BlockTriggerRecord, _Mapping]]] = ...,
    ) -> None: ...

class BlockTriggerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BlockRange(_message.Message):
    __slots__ = ("prefix", "records", "error")
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    RECORDS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    prefix: Prefix
    records: _containers.RepeatedCompositeFieldContainer[BlockRecord]
    error: Error
    def __init__(
        self,
        prefix: _Optional[_Union[Prefix, _Mapping]] = ...,
        records: _Optional[_Iterable[_Union[BlockRecord, _Mapping]]] = ...,
        error: _Optional[_Union[Error, _Mapping]] = ...,
    ) -> None: ...

class BlockRecord(_message.Message):
    __slots__ = ("record_offset", "record_size", "record")
    RECORD_OFFSET_FIELD_NUMBER: _ClassVar[int]
    RECORD_SIZE_FIELD_NUMBER: _ClassVar[int]
    RECORD_FIELD_NUMBER: _ClassVar[int]
    record_offset: int
    record_size: int
    record: Record
    def __init__(
        self,
        record_offset: _Optional[int] = ...,
        record_size: _Optional[int] = ...,
        record: _Optional[_Union[Record, _Mapping]] = ...,
    ) -> None: ...

class BlockEntry(_message.Message):
    __slots__ = ("partition_number", "block_id", "block_size", "created_at", "error")
    PARTITION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    partition_number: int
    block_id: int
    block_size: int
    created_at: _timestamp_pb2.Timestamp
    error: Error
    def __init__(
        self,
        partition_number: _Optional[int] = ...,
        block_id: _Optional[int] = ...,
        block_size: _Optional[int] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
        error: _Optional[_Union[Error, _Mapping]] = ...,
    ) -> None: ...

class GetBlockRangesRequest(_message.Message):
    __slots__ = ("ranges",)
    RANGES_FIELD_NUMBER: _ClassVar[int]
    ranges: _containers.RepeatedCompositeFieldContainer[Range]
    def __init__(
        self, ranges: _Optional[_Iterable[_Union[Range, _Mapping]]] = ...
    ) -> None: ...

class GetBlockRangesResponse(_message.Message):
    __slots__ = ("ranges",)
    RANGES_FIELD_NUMBER: _ClassVar[int]
    ranges: _containers.RepeatedCompositeFieldContainer[BlockRange]
    def __init__(
        self, ranges: _Optional[_Iterable[_Union[BlockRange, _Mapping]]] = ...
    ) -> None: ...

class GetBlockMetadataRequest(_message.Message):
    __slots__ = ("prefixes",)
    PREFIXES_FIELD_NUMBER: _ClassVar[int]
    prefixes: _containers.RepeatedCompositeFieldContainer[Prefix]
    def __init__(
        self, prefixes: _Optional[_Iterable[_Union[Prefix, _Mapping]]] = ...
    ) -> None: ...

class GetBlockMetadataResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[BlockEntry]
    def __init__(
        self, entries: _Optional[_Iterable[_Union[BlockEntry, _Mapping]]] = ...
    ) -> None: ...

class ScanBlocksRequest(_message.Message):
    __slots__ = ("partition_number", "start_block_id", "limit")
    PARTITION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    START_BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    partition_number: int
    start_block_id: int
    limit: int
    def __init__(
        self,
        partition_number: _Optional[int] = ...,
        start_block_id: _Optional[int] = ...,
        limit: _Optional[int] = ...,
    ) -> None: ...

class ScanBlocksResponse(_message.Message):
    __slots__ = ("block_id", "block_size", "created_at")
    BLOCK_ID_FIELD_NUMBER: _ClassVar[int]
    BLOCK_SIZE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    block_id: int
    block_size: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(
        self,
        block_id: _Optional[int] = ...,
        block_size: _Optional[int] = ...,
        created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...,
    ) -> None: ...
