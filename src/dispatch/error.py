from builtins import TimeoutError as _TimeoutError
from typing import cast

from dispatch.status import Status, register_error_type


class DispatchError(Exception):
    """Base class for Dispatch exceptions."""

    _status = Status.UNSPECIFIED


class TimeoutError(DispatchError, _TimeoutError):
    """Operation timed out."""

    _status = Status.TIMEOUT


class ThrottleError(DispatchError):
    """Operation was throttled."""

    _status = Status.THROTTLED


class InvalidArgumentError(DispatchError, ValueError):
    """Invalid argument was received."""

    _status = Status.INVALID_ARGUMENT


class InvalidResponseError(DispatchError, ValueError):
    """Invalid response was received."""

    _status = Status.INVALID_RESPONSE


class TemporaryError(DispatchError):
    """Generic temporary error. Used in cases where a more specific
    error class is not available, but the operation that failed should
    be attempted again."""

    _status = Status.TEMPORARY_ERROR


class PermanentError(DispatchError):
    """Generic permanent error. Used in cases where a more specific
    error class is not available, but the operation that failed should
    *not* be attempted again."""

    _status = Status.PERMANENT_ERROR


class IncompatibleStateError(DispatchError):
    """Coroutine state is incompatible with the current interpreter
    and application revision."""

    _status = Status.INCOMPATIBLE_STATE


class DNSError(DispatchError, ConnectionError):
    """Generic DNS error. Used in cases where a more specific error class is
    not available, but the operation that failed should be attempted again."""

    _status = Status.DNS_ERROR


class TCPError(DispatchError, ConnectionError):
    """Generic TCP error. Used in cases where a more specific error class is
    not available, but the operation that failed should be attempted again."""

    _status = Status.TCP_ERROR


class HTTPError(DispatchError, ConnectionError):
    """Generic HTTP error. Used in cases where a more specific error class is
    not available, but the operation that failed should be attempted again."""

    _status = Status.HTTP_ERROR


class UnauthenticatedError(DispatchError):
    """The caller did not authenticate with the resource."""

    _status = Status.UNAUTHENTICATED


class PermissionDeniedError(DispatchError, PermissionError):
    """The caller does not have access to the resource."""

    _status = Status.PERMISSION_DENIED


class NotFoundError(DispatchError):
    """Generic not found error. Used in cases where a more specific error class
    is not available, but the operation that failed should *not* be attempted
    again."""

    _status = Status.NOT_FOUND


def dispatch_error_status(error: Exception) -> Status:
    return cast(DispatchError, error)._status


register_error_type(DispatchError, dispatch_error_status)
