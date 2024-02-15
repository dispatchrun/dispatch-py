from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper

DESCRIPTOR: _descriptor.FileDescriptor

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNSPECIFIED: _ClassVar[Status]
    STATUS_OK: _ClassVar[Status]
    STATUS_TIMEOUT: _ClassVar[Status]
    STATUS_THROTTLED: _ClassVar[Status]
    STATUS_INVALID_ARGUMENT: _ClassVar[Status]
    STATUS_INVALID_RESPONSE: _ClassVar[Status]
    STATUS_TEMPORARY_ERROR: _ClassVar[Status]
    STATUS_PERMANENT_ERROR: _ClassVar[Status]
    STATUS_INCOMPATIBLE_STATE: _ClassVar[Status]
    STATUS_DNS_ERROR: _ClassVar[Status]
    STATUS_TCP_ERROR: _ClassVar[Status]
    STATUS_TLS_ERROR: _ClassVar[Status]
    STATUS_HTTP_ERROR: _ClassVar[Status]
    STATUS_UNAUTHENTICATED: _ClassVar[Status]
    STATUS_PERMISSION_DENIED: _ClassVar[Status]
    STATUS_NOT_FOUND: _ClassVar[Status]

STATUS_UNSPECIFIED: Status
STATUS_OK: Status
STATUS_TIMEOUT: Status
STATUS_THROTTLED: Status
STATUS_INVALID_ARGUMENT: Status
STATUS_INVALID_RESPONSE: Status
STATUS_TEMPORARY_ERROR: Status
STATUS_PERMANENT_ERROR: Status
STATUS_INCOMPATIBLE_STATE: Status
STATUS_DNS_ERROR: Status
STATUS_TCP_ERROR: Status
STATUS_TLS_ERROR: Status
STATUS_HTTP_ERROR: Status
STATUS_UNAUTHENTICATED: Status
STATUS_PERMISSION_DENIED: Status
STATUS_NOT_FOUND: Status
