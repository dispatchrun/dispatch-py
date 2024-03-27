import unittest

from dispatch.integrations.http import http_response_code_status
from dispatch.status import Status, status_for_error


class TestErrorStatus(unittest.TestCase):
    def test_status_for_Exception(self):
        assert status_for_error(Exception()) is Status.PERMANENT_ERROR

    def test_status_for_ValueError(self):
        assert status_for_error(ValueError()) is Status.INVALID_ARGUMENT

    def test_status_for_TypeError(self):
        assert status_for_error(TypeError()) is Status.INVALID_ARGUMENT

    def test_status_for_KeyError(self):
        assert status_for_error(KeyError()) is Status.PERMANENT_ERROR

    def test_status_for_EOFError(self):
        assert status_for_error(EOFError()) is Status.TEMPORARY_ERROR

    def test_status_for_ConnectionError(self):
        assert status_for_error(ConnectionError()) is Status.TCP_ERROR

    def test_status_for_PermissionError(self):
        assert status_for_error(PermissionError()) is Status.PERMISSION_DENIED

    def test_status_for_FileNotFoundError(self):
        assert status_for_error(FileNotFoundError()) is Status.NOT_FOUND

    def test_status_for_InterruptedError(self):
        assert status_for_error(InterruptedError()) is Status.TEMPORARY_ERROR

    def test_status_for_KeyboardInterrupt(self):
        assert status_for_error(KeyboardInterrupt()) is Status.TEMPORARY_ERROR

    def test_status_for_OSError(self):
        assert status_for_error(OSError()) is Status.TEMPORARY_ERROR

    def test_status_for_TimeoutError(self):
        assert status_for_error(TimeoutError()) is Status.TIMEOUT

    def test_status_for_BaseException(self):
        assert status_for_error(BaseException()) is Status.PERMANENT_ERROR

    def test_status_for_custom_error(self):
        class CustomError(Exception):
            pass

        assert status_for_error(CustomError()) is Status.PERMANENT_ERROR

    def test_status_for_custom_error_with_handler(self):
        class CustomError(Exception):
            pass

        def handler(error: Exception) -> Status:
            return Status.OK

        from dispatch.status import register_error_type

        register_error_type(CustomError, handler)
        assert status_for_error(CustomError()) is Status.OK

    def test_status_for_custom_timeout(self):
        class CustomError(TimeoutError):
            pass

        assert status_for_error(CustomError()) is Status.TIMEOUT


class TestHTTPStatusCodes(unittest.TestCase):
    def test_http_response_code_status_400(self):
        assert http_response_code_status(400) is Status.INVALID_ARGUMENT

    def test_http_response_code_status_401(self):
        assert http_response_code_status(401) is Status.UNAUTHENTICATED

    def test_http_response_code_status_403(self):
        assert http_response_code_status(403) is Status.PERMISSION_DENIED

    def test_http_response_code_status_404(self):
        assert http_response_code_status(404) is Status.NOT_FOUND

    def test_http_response_code_status_408(self):
        assert http_response_code_status(408) is Status.TIMEOUT

    def test_http_response_code_status_429(self):
        assert http_response_code_status(429) is Status.THROTTLED

    def test_http_response_code_status_501(self):
        assert http_response_code_status(501) is Status.PERMANENT_ERROR

    def test_http_response_code_status_1xx(self):
        for status in range(100, 200):
            assert http_response_code_status(100) is Status.PERMANENT_ERROR

    def test_http_response_code_status_2xx(self):
        for status in range(200, 300):
            assert http_response_code_status(200) is Status.OK

    def test_http_response_code_status_3xx(self):
        for status in range(300, 400):
            assert http_response_code_status(300) is Status.PERMANENT_ERROR

    def test_http_response_code_status_4xx(self):
        for status in range(400, 500):
            if status not in (400, 401, 403, 404, 408, 429, 501):
                assert http_response_code_status(status) is Status.PERMANENT_ERROR

    def test_http_response_code_status_5xx(self):
        for status in range(500, 600):
            if status not in (501,):
                assert http_response_code_status(status) is Status.TEMPORARY_ERROR

    def test_http_response_code_status_6xx(self):
        for status in range(600, 700):
            assert http_response_code_status(600) is Status.UNSPECIFIED
