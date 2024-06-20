import traceback

import pytest

from dispatch.proto import Error, Status


def test_error_with_ok_status():
    with pytest.raises(ValueError):
        Error(Status.OK, type="type", message="yep")


def test_from_exception_timeout():
    err = Error.from_exception(TimeoutError())
    assert Status.TIMEOUT == err.status


def test_from_exception_syntax_error():
    err = Error.from_exception(SyntaxError())
    assert Status.PERMANENT_ERROR == err.status


def test_conversion_between_exception_and_error():
    try:
        raise ValueError("test")
    except Exception as e:
        original_exception = e
        error = Error.from_exception(e)
    original_traceback = "".join(
        traceback.format_exception(
            original_exception.__class__,
            original_exception,
            original_exception.__traceback__,
        )
    )

    # For some reasons traceback.format_exception does not include the caret
    # (^) in the original traceback, but it does in the reconstructed one,
    # so we strip it out to be able to compare the two.
    def strip_caret(s):
        return "\n".join([l for l in s.split("\n") if not l.strip().startswith("^")])

    reconstructed_exception = error.to_exception()
    reconstructed_traceback = strip_caret(
        "".join(
            traceback.format_exception(
                reconstructed_exception.__class__,
                reconstructed_exception,
                reconstructed_exception.__traceback__,
            )
        )
    )

    assert type(reconstructed_exception) is type(original_exception)
    assert str(reconstructed_exception) == str(original_exception)
    assert original_traceback == reconstructed_traceback

    error2 = Error.from_exception(reconstructed_exception)
    reconstructed_exception2 = error2.to_exception()
    reconstructed_traceback2 = strip_caret(
        "".join(
            traceback.format_exception(
                reconstructed_exception2.__class__,
                reconstructed_exception2,
                reconstructed_exception2.__traceback__,
            )
        )
    )

    assert type(reconstructed_exception2) is type(original_exception)
    assert str(reconstructed_exception2) == str(original_exception)
    assert original_traceback == reconstructed_traceback2


def test_conversion_without_traceback():
    try:
        raise ValueError("test")
    except Exception as e:
        original_exception = e

    error = Error.from_exception(original_exception)
    error.traceback = b""

    reconstructed_exception = error.to_exception()
    assert type(reconstructed_exception) is type(original_exception)
    assert str(reconstructed_exception) == str(original_exception)
