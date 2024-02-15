import unittest

from dispatch.status import Status, status_for_error


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
