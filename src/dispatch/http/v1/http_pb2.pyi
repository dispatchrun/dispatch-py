from dispatch.security.v1 import security_pb2 as _security_pb2
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

class Request(_message.Message):
    __slots__ = ("method", "url", "header", "body", "network_access_control")
    METHOD_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    HEADER_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ACCESS_CONTROL_FIELD_NUMBER: _ClassVar[int]
    method: str
    url: str
    header: _containers.RepeatedCompositeFieldContainer[Header]
    body: bytes
    network_access_control: _security_pb2.NetworkAccessControl
    def __init__(
        self,
        method: _Optional[str] = ...,
        url: _Optional[str] = ...,
        header: _Optional[_Iterable[_Union[Header, _Mapping]]] = ...,
        body: _Optional[bytes] = ...,
        network_access_control: _Optional[
            _Union[_security_pb2.NetworkAccessControl, _Mapping]
        ] = ...,
    ) -> None: ...

class Response(_message.Message):
    __slots__ = ("status_code", "header", "body")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    HEADER_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    status_code: int
    header: _containers.RepeatedCompositeFieldContainer[Header]
    body: bytes
    def __init__(
        self,
        status_code: _Optional[int] = ...,
        header: _Optional[_Iterable[_Union[Header, _Mapping]]] = ...,
        body: _Optional[bytes] = ...,
    ) -> None: ...

class Header(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    def __init__(
        self, name: _Optional[str] = ..., value: _Optional[str] = ...
    ) -> None: ...
