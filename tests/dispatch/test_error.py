import traceback
import unittest
from pprint import pprint

from dispatch.proto import Error


class TestError(unittest.TestCase):

    def test_conversion_between_exception_and_error(self):
        try:
            raise ValueError("test")
        except Exception as e:
            original_exception = e
            error = Error.from_exception(e)
        original_traceback = "".join(traceback.format_exception(original_exception))

        # For some reasons traceback.format_exception does not include the caret
        # (^) in the original traceback, but it does in the reconstructed one,
        # so we strip it out to be able to compare the two.
        reconstructed_exception = error.to_exception()
        reconstructed_traceback = "".join(
            traceback.format_exception(reconstructed_exception)
        )
        reconstructed_traceback = [
            s
            for s in reconstructed_traceback.split("\n")
            if not s.strip().startswith("^")
        ]
        reconstructed_traceback = "\n".join(reconstructed_traceback)

        assert type(reconstructed_exception) is type(original_exception)
        assert str(reconstructed_exception) == str(original_exception)
        assert original_traceback == reconstructed_traceback
