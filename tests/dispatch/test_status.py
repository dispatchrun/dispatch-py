import unittest

from dispatch.status import Status, status_for_error
from dispatch.integrations.http import http_response_code_status

class TestErrorStatus(unittest.TestCase):

    def test_status_for_Exception(self):
        self.assertEqual(status_for_error(Exception()), Status.PERMANENT_ERROR)

    def test_status_for_ValueError(self):
        self.assertEqual(status_for_error(ValueError()), Status.INVALID_ARGUMENT)

    def test_status_for_TypeError(self):
        self.assertEqual(status_for_error(TypeError()), Status.INVALID_ARGUMENT)

    def test_status_for_KeyError(self):
        self.assertEqual(status_for_error(KeyError()), Status.PERMANENT_ERROR)

    def test_status_for_EOFError(self):
        self.assertEqual(status_for_error(EOFError()), Status.TEMPORARY_ERROR)

    def test_status_for_ConnectionError(self):
        self.assertEqual(status_for_error(ConnectionError()), Status.TCP_ERROR)

    def test_status_for_PermissionError(self):
        self.assertEqual(status_for_error(PermissionError()), Status.PERMISSION_DENIED)

    def test_status_for_FileNotFoundError(self):
        self.assertEqual(status_for_error(FileNotFoundError()), Status.NOT_FOUND)

    def test_status_for_InterruptedError(self):
        self.assertEqual(status_for_error(InterruptedError()), Status.TEMPORARY_ERROR)

    def test_status_for_KeyboardInterrupt(self):
        self.assertEqual(status_for_error(KeyboardInterrupt()), Status.TEMPORARY_ERROR)

    def test_status_for_OSError(self):
        self.assertEqual(status_for_error(OSError()), Status.TEMPORARY_ERROR)

    def test_status_for_TimeoutError(self):
        self.assertEqual(status_for_error(TimeoutError()), Status.TIMEOUT)

    def test_status_for_BaseException(self):
        self.assertEqual(status_for_error(BaseException()), Status.PERMANENT_ERROR)

    def test_status_for_custom_error(self):
        class CustomError(Exception):
            pass

        self.assertEqual(status_for_error(CustomError()), Status.PERMANENT_ERROR)

    def test_status_for_custom_error_with_handler(self):
        class CustomError(Exception):
            pass

        def handler(error: Exception) -> Status:
            return Status.OK

        from dispatch.status import register_error_type

        register_error_type(CustomError, handler)
        self.assertEqual(status_for_error(CustomError()), Status.OK)

class TestHTTPStatusCodes(unittest.TestCase):

    def test_http_response_code_status_400(self):
        self.assertEqual(http_response_code_status(400), Status.INVALID_ARGUMENT)

    def test_http_response_code_status_401(self):
        self.assertEqual(http_response_code_status(401), Status.UNAUTHENTICATED)

    def test_http_response_code_status_403(self):
        self.assertEqual(http_response_code_status(403), Status.PERMISSION_DENIED)

    def test_http_response_code_status_404(self):
        self.assertEqual(http_response_code_status(404), Status.NOT_FOUND)

    def test_http_response_code_status_408(self):
        self.assertEqual(http_response_code_status(408), Status.TIMEOUT)

    def test_http_response_code_status_429(self):
        self.assertEqual(http_response_code_status(429), Status.THROTTLED)

    def test_http_response_code_status_501(self):
        self.assertEqual(http_response_code_status(501), Status.PERMANENT_ERROR)

    def test_http_response_code_status_1xx(self):
        for status in range(100, 200):
            self.assertEqual(http_response_code_status(100), Status.PERMANENT_ERROR)

    def test_http_response_code_status_2xx(self):
        for status in range(200, 300):
            self.assertEqual(http_response_code_status(200), Status.OK)

    def test_http_response_code_status_3xx(self):
        for status in range(300, 400):
            self.assertEqual(http_response_code_status(300), Status.PERMANENT_ERROR)

    def test_http_response_code_status_4xx(self):
        for status in range(400, 500):
            if status not in (400, 401, 403, 404, 408, 429, 501):
                self.assertEqual(http_response_code_status(status), Status.PERMANENT_ERROR)

    def test_http_response_code_status_5xx(self):
        for status in range(500, 600):
            if status not in (501,):
                self.assertEqual(http_response_code_status(status), Status.TEMPORARY_ERROR)

    def test_http_response_code_status_6xx(self):
        for status in range(600, 700):
            self.assertEqual(http_response_code_status(600), Status.UNSPECIFIED)
