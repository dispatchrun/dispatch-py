import enum
from typing import Any, Callable, Type

from dispatch.error import IncompatibleStateError
from dispatch.sdk.v1 import status_pb2 as status_pb


@enum.unique
class Status(int, enum.Enum):
    """Enumeration of the possible values that can be used in the return status
    of functions.
    """

    UNSPECIFIED = status_pb.STATUS_UNSPECIFIED
    OK = status_pb.STATUS_OK
    TIMEOUT = status_pb.STATUS_TIMEOUT
    THROTTLED = status_pb.STATUS_THROTTLED
    INVALID_ARGUMENT = status_pb.STATUS_INVALID_ARGUMENT
    INVALID_RESPONSE = status_pb.STATUS_INVALID_RESPONSE
    TEMPORARY_ERROR = status_pb.STATUS_TEMPORARY_ERROR
    PERMANENT_ERROR = status_pb.STATUS_PERMANENT_ERROR
    INCOMPATIBLE_STATE = status_pb.STATUS_INCOMPATIBLE_STATE
    DNS_ERROR = status_pb.STATUS_DNS_ERROR
    TCP_ERROR = status_pb.STATUS_TCP_ERROR
    TLS_ERROR = status_pb.STATUS_TLS_ERROR
    HTTP_ERROR = status_pb.STATUS_HTTP_ERROR
    UNAUTHENTICATED = status_pb.STATUS_UNAUTHENTICATED
    PERMISSION_DENIED = status_pb.STATUS_PERMISSION_DENIED
    NOT_FOUND = status_pb.STATUS_NOT_FOUND

    _proto: status_pb.Status

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


# Maybe we should find a better way to define that enum. It's that way to please
# Mypy and provide documentation for the enum values.

Status.UNSPECIFIED.__doc__ = "Status not specified (default)"
Status.UNSPECIFIED._proto = status_pb.STATUS_UNSPECIFIED
Status.OK.__doc__ = "Coroutine returned as expected"
Status.OK._proto = status_pb.STATUS_OK
Status.TIMEOUT.__doc__ = "Coroutine encountered a timeout and may be retried"
Status.TIMEOUT._proto = status_pb.STATUS_TIMEOUT
Status.THROTTLED.__doc__ = "Coroutine was throttled and may be retried later"
Status.THROTTLED._proto = status_pb.STATUS_THROTTLED
Status.INVALID_ARGUMENT.__doc__ = "Coroutine was provided an invalid type of input"
Status.INVALID_ARGUMENT._proto = status_pb.STATUS_INVALID_ARGUMENT
Status.INVALID_RESPONSE.__doc__ = "Coroutine was provided an unexpected response"
Status.INVALID_RESPONSE._proto = status_pb.STATUS_INVALID_RESPONSE
Status.TEMPORARY_ERROR.__doc__ = (
    "Coroutine encountered a temporary error, may be retried"
)
Status.TEMPORARY_ERROR._proto = status_pb.STATUS_TEMPORARY_ERROR
Status.PERMANENT_ERROR.__doc__ = (
    "Coroutine encountered a permanent error, should not be retried"
)
Status.PERMANENT_ERROR._proto = status_pb.STATUS_PERMANENT_ERROR
Status.INCOMPATIBLE_STATE.__doc__ = (
    "Coroutine was provided an incompatible state. May be restarted from scratch"
)
Status.INCOMPATIBLE_STATE._proto = status_pb.STATUS_INCOMPATIBLE_STATE
Status.DNS_ERROR.__doc__ = "Coroutine encountered a DNS error"
Status.DNS_ERROR._proto = status_pb.STATUS_DNS_ERROR
Status.TCP_ERROR.__doc__ = "Coroutine encountered a TCP error"
Status.TCP_ERROR._proto = status_pb.STATUS_TCP_ERROR
Status.TLS_ERROR.__doc__ = "Coroutine encountered a TLS error"
Status.TLS_ERROR._proto = status_pb.STATUS_TLS_ERROR
Status.HTTP_ERROR.__doc__ = "Coroutine encountered an HTTP error"
Status.HTTP_ERROR._proto = status_pb.STATUS_HTTP_ERROR
Status.UNAUTHENTICATED.__doc__ = "An operation was performed without authentication"
Status.UNAUTHENTICATED._proto = status_pb.STATUS_UNAUTHENTICATED
Status.PERMISSION_DENIED.__doc__ = "An operation was performed without permission"
Status.PERMISSION_DENIED._proto = status_pb.STATUS_PERMISSION_DENIED
Status.NOT_FOUND.__doc__ = "An operation was performed on a non-existent resource"
Status.NOT_FOUND._proto = status_pb.STATUS_NOT_FOUND

_ERROR_TYPES: dict[Type[Exception], Callable[[Exception], Status]] = {}
_OUTPUT_TYPES: dict[Type[Any], Callable[[Any], Status]] = {}


def status_for_error(error: Exception) -> Status:
    """Returns a Status that corresponds to the specified error."""
    # See if the error matches one of the registered types.
    handler = _find_handler(error, _ERROR_TYPES)
    if handler is not None:
        return handler(error)
    # If not, resort to standard error categorization.
    #
    # See https://docs.python.org/3/library/exceptions.html
    match error:
        case IncompatibleStateError():
            return Status.INCOMPATIBLE_STATE
        case TimeoutError():
            return Status.TIMEOUT
        case TypeError() | ValueError():
            return Status.INVALID_ARGUMENT
        case ConnectionError():
            return Status.TCP_ERROR
        case PermissionError():
            return Status.PERMISSION_DENIED
        case FileNotFoundError():
            return Status.NOT_FOUND
        case EOFError() | InterruptedError() | KeyboardInterrupt() | OSError():
            # For OSError, we might want to categorize the values of errnon
            # to determine whether the error is temporary or permanent.
            #
            # In general, permanent errors from the OS are rare because they
            # tend to be caused by invalid use of syscalls, which are
            # unlikely at higher abstraction levels.
            return Status.TEMPORARY_ERROR
    return Status.PERMANENT_ERROR


def status_for_output(output: Any) -> Status:
    """Returns a Status that corresponds to the specified output value."""
    # See if the output value matches one of the registered types.
    handler = _find_handler(output, _OUTPUT_TYPES)
    if handler is not None:
        return handler(output)

    return Status.OK


def register_error_type(
    error_type: Type[Exception], handler: Callable[[Exception], Status]
):
    """Register an error type, and a handler which derives a Status from
    errors of this type."""
    _ERROR_TYPES[error_type] = handler


def register_output_type(output_type: Type[Any], handler: Callable[[Any], Status]):
    """Register an output type, and a handler which derives a Status from
    outputs of this type."""
    _OUTPUT_TYPES[output_type] = handler


def _find_handler(obj, types):
    for cls in type(obj).__mro__:
        try:
            return types[cls]
        except KeyError:
            pass

    return None  # not found
