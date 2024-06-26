import pickle
from datetime import datetime, timedelta

from dispatch.any import marshal_any, unmarshal_any
from dispatch.sdk.v1 import error_pb2 as error_pb


def test_unmarshal_none():
    boxed = marshal_any(None)
    assert None == unmarshal_any(boxed)


def test_unmarshal_bool():
    boxed = marshal_any(True)
    assert True == unmarshal_any(boxed)


def test_unmarshal_integer():
    boxed = marshal_any(1234)
    assert 1234 == unmarshal_any(boxed)

    boxed = marshal_any(-1234)
    assert -1234 == unmarshal_any(boxed)


def test_unmarshal_float():
    boxed = marshal_any(3.14)
    assert 3.14 == unmarshal_any(boxed)


def test_unmarshal_string():
    boxed = marshal_any("foo")
    assert "foo" == unmarshal_any(boxed)


def test_unmarshal_bytes():
    boxed = marshal_any(b"bar")
    assert b"bar" == unmarshal_any(boxed)


def test_unmarshal_timestamp():
    ts = datetime.fromtimestamp(
        1719372909.641448
    )  # datetime.datetime(2024, 6, 26, 13, 35, 9, 641448)
    boxed = marshal_any(ts)
    assert ts == unmarshal_any(boxed)


def test_unmarshal_duration():
    d = timedelta(seconds=1, microseconds=1234)
    boxed = marshal_any(d)
    assert d == unmarshal_any(boxed)


def test_unmarshal_protobuf_message():
    message = error_pb.Error(type="internal", message="oops")
    boxed = marshal_any(message)

    # Check the message isn't pickled (in which case the type_url would
    # end with dispatch.sdk.python.v1.Pickled).
    assert (
        "buf.build/stealthrocket/dispatch-proto/dispatch.sdk.v1.Error" == boxed.type_url
    )

    assert message == unmarshal_any(boxed)
