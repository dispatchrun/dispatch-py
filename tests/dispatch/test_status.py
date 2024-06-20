from typing import Any

from dispatch import error
from dispatch.integrations.http import http_response_code_status
from dispatch.status import (
    Status,
    register_error_type,
    register_output_type,
    status_for_error,
    status_for_output,
)


def test_status_for_Exception():
    assert status_for_error(Exception()) is Status.PERMANENT_ERROR


def test_status_for_ValueError():
    assert status_for_error(ValueError()) is Status.INVALID_ARGUMENT


def test_status_for_TypeError():
    assert status_for_error(TypeError()) is Status.INVALID_ARGUMENT


def test_status_for_KeyError():
    assert status_for_error(KeyError()) is Status.PERMANENT_ERROR


def test_status_for_EOFError():
    assert status_for_error(EOFError()) is Status.TEMPORARY_ERROR


def test_status_for_ConnectionError():
    assert status_for_error(ConnectionError()) is Status.TCP_ERROR


def test_status_for_PermissionError():
    assert status_for_error(PermissionError()) is Status.PERMISSION_DENIED


def test_status_for_FileNotFoundError():
    assert status_for_error(FileNotFoundError()) is Status.NOT_FOUND


def test_status_for_InterruptedError():
    assert status_for_error(InterruptedError()) is Status.TEMPORARY_ERROR


def test_status_for_KeyboardInterrupt():
    assert status_for_error(KeyboardInterrupt()) is Status.TEMPORARY_ERROR


def test_status_for_OSError():
    assert status_for_error(OSError()) is Status.TEMPORARY_ERROR


def test_status_for_TimeoutError():
    assert status_for_error(TimeoutError()) is Status.TIMEOUT


def test_status_for_BaseException():
    assert status_for_error(BaseException()) is Status.PERMANENT_ERROR


def test_status_for_custom_error():
    class CustomError(Exception):
        pass

    assert status_for_error(CustomError()) is Status.PERMANENT_ERROR


def test_status_for_custom_error_with_handler():
    class CustomError(Exception):
        pass

    def handler(error: Exception) -> Status:
        assert isinstance(error, CustomError)
        return Status.OK

    register_error_type(CustomError, handler)
    assert status_for_error(CustomError()) is Status.OK


def test_status_for_custom_error_with_base_handler():
    class CustomBaseError(Exception):
        pass

    class CustomError(CustomBaseError):
        pass

    def handler(error: Exception) -> Status:
        assert isinstance(error, CustomBaseError)
        assert isinstance(error, CustomError)
        return Status.TCP_ERROR

    register_error_type(CustomBaseError, handler)
    assert status_for_error(CustomError()) is Status.TCP_ERROR


def test_status_for_custom_error_with_status():
    class CustomError(Exception):
        pass

    register_error_type(CustomError, Status.THROTTLED)
    assert status_for_error(CustomError()) is Status.THROTTLED


def test_status_for_custom_error_with_base_status():
    class CustomBaseError(Exception):
        pass

    class CustomError(CustomBaseError):
        pass

    class CustomError2(CustomBaseError):
        pass

    register_error_type(CustomBaseError, Status.THROTTLED)
    register_error_type(CustomError2, Status.INVALID_ARGUMENT)
    assert status_for_error(CustomError()) is Status.THROTTLED
    assert status_for_error(CustomError2()) is Status.INVALID_ARGUMENT


def test_status_for_custom_timeout():
    class CustomError(TimeoutError):
        pass

    assert status_for_error(CustomError()) is Status.TIMEOUT


def test_status_for_DispatchError():
    assert status_for_error(error.TimeoutError()) is Status.TIMEOUT
    assert status_for_error(error.ThrottleError()) is Status.THROTTLED
    assert status_for_error(error.InvalidArgumentError()) is Status.INVALID_ARGUMENT
    assert status_for_error(error.InvalidResponseError()) is Status.INVALID_RESPONSE
    assert status_for_error(error.TemporaryError()) is Status.TEMPORARY_ERROR
    assert status_for_error(error.PermanentError()) is Status.PERMANENT_ERROR
    assert status_for_error(error.IncompatibleStateError()) is Status.INCOMPATIBLE_STATE
    assert status_for_error(error.DNSError()) is Status.DNS_ERROR
    assert status_for_error(error.TCPError()) is Status.TCP_ERROR
    assert status_for_error(error.HTTPError()) is Status.HTTP_ERROR
    assert status_for_error(error.UnauthenticatedError()) is Status.UNAUTHENTICATED
    assert status_for_error(error.PermissionDeniedError()) is Status.PERMISSION_DENIED
    assert status_for_error(error.NotFoundError()) is Status.NOT_FOUND
    assert status_for_error(error.DispatchError()) is Status.UNSPECIFIED


def test_status_for_custom_output():
    class CustomOutput:
        pass

    assert status_for_output(CustomOutput()) is Status.OK  # default


def test_status_for_custom_output_with_handler():
    class CustomOutput:
        pass

    def handler(output: Any) -> Status:
        assert isinstance(output, CustomOutput)
        return Status.DNS_ERROR

    register_output_type(CustomOutput, handler)
    assert status_for_output(CustomOutput()) is Status.DNS_ERROR


def test_status_for_custom_output_with_base_handler():
    class CustomOutputBase:
        pass

    class CustomOutputError(CustomOutputBase):
        pass

    class CustomOutputSuccess(CustomOutputBase):
        pass

    def handler(output: Any) -> Status:
        assert isinstance(output, CustomOutputBase)
        if isinstance(output, CustomOutputError):
            return Status.DNS_ERROR
        assert isinstance(output, CustomOutputSuccess)
        return Status.OK

    register_output_type(CustomOutputBase, handler)
    assert status_for_output(CustomOutputSuccess()) is Status.OK
    assert status_for_output(CustomOutputError()) is Status.DNS_ERROR


def test_status_for_custom_output_with_status():
    class CustomOutputBase:
        pass

    class CustomOutputChild1(CustomOutputBase):
        pass

    class CustomOutputChild2(CustomOutputBase):
        pass

    register_output_type(CustomOutputBase, Status.PERMISSION_DENIED)
    register_output_type(CustomOutputChild1, Status.TCP_ERROR)
    assert status_for_output(CustomOutputChild1()) is Status.TCP_ERROR
    assert status_for_output(CustomOutputChild2()) is Status.PERMISSION_DENIED


def test_status_for_custom_output_with_base_status():
    class CustomOutput(Exception):
        pass

    register_output_type(CustomOutput, Status.THROTTLED)
    assert status_for_output(CustomOutput()) is Status.THROTTLED


def test_http_response_code_status_400():
    assert http_response_code_status(400) is Status.INVALID_ARGUMENT


def test_http_response_code_status_401():
    assert http_response_code_status(401) is Status.UNAUTHENTICATED


def test_http_response_code_status_403():
    assert http_response_code_status(403) is Status.PERMISSION_DENIED


def test_http_response_code_status_404():
    assert http_response_code_status(404) is Status.NOT_FOUND


def test_http_response_code_status_408():
    assert http_response_code_status(408) is Status.TIMEOUT


def test_http_response_code_status_429():
    assert http_response_code_status(429) is Status.THROTTLED


def test_http_response_code_status_501():
    assert http_response_code_status(501) is Status.PERMANENT_ERROR


def test_http_response_code_status_1xx():
    for status in range(100, 200):
        assert http_response_code_status(100) is Status.PERMANENT_ERROR


def test_http_response_code_status_2xx():
    for status in range(200, 300):
        assert http_response_code_status(200) is Status.OK


def test_http_response_code_status_3xx():
    for status in range(300, 400):
        assert http_response_code_status(300) is Status.PERMANENT_ERROR


def test_http_response_code_status_4xx():
    for status in range(400, 500):
        if status not in (400, 401, 403, 404, 408, 429, 501):
            assert http_response_code_status(status) is Status.PERMANENT_ERROR


def test_http_response_code_status_5xx():
    for status in range(500, 600):
        if status not in (501,):
            assert http_response_code_status(status) is Status.TEMPORARY_ERROR


def test_http_response_code_status_6xx():
    for status in range(600, 700):
        assert http_response_code_status(600) is Status.UNSPECIFIED
