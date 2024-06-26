import pickle
from datetime import UTC, datetime, timedelta

from dispatch.any import INT64_MAX, INT64_MIN, marshal_any, unmarshal_any
from dispatch.sdk.v1 import error_pb2 as error_pb


def test_unmarshal_none():
    boxed = marshal_any(None)
    assert "type.googleapis.com/google.protobuf.Empty" == boxed.type_url
    assert None == unmarshal_any(boxed)


def test_unmarshal_bool():
    boxed = marshal_any(True)
    assert "type.googleapis.com/google.protobuf.BoolValue" == boxed.type_url
    assert True == unmarshal_any(boxed)


def test_unmarshal_integer():
    boxed = marshal_any(1234)
    assert "type.googleapis.com/google.protobuf.Int64Value" == boxed.type_url
    assert 1234 == unmarshal_any(boxed)

    boxed = marshal_any(-1234)
    assert "type.googleapis.com/google.protobuf.Int64Value" == boxed.type_url
    assert -1234 == unmarshal_any(boxed)


def test_unmarshal_int64_limits():
    boxed = marshal_any(INT64_MIN)
    assert "type.googleapis.com/google.protobuf.Int64Value" == boxed.type_url
    assert INT64_MIN == unmarshal_any(boxed)

    boxed = marshal_any(INT64_MAX)
    assert "type.googleapis.com/google.protobuf.Int64Value" == boxed.type_url
    assert INT64_MAX == unmarshal_any(boxed)

    boxed = marshal_any(INT64_MIN - 1)
    assert (
        "buf.build/stealthrocket/dispatch-proto/dispatch.sdk.python.v1.Pickled"
        == boxed.type_url
    )
    assert INT64_MIN - 1 == unmarshal_any(boxed)

    boxed = marshal_any(INT64_MAX + 1)
    assert (
        "buf.build/stealthrocket/dispatch-proto/dispatch.sdk.python.v1.Pickled"
        == boxed.type_url
    )
    assert INT64_MAX + 1 == unmarshal_any(boxed)


def test_unmarshal_float():
    boxed = marshal_any(3.14)
    assert "type.googleapis.com/google.protobuf.DoubleValue" == boxed.type_url
    assert 3.14 == unmarshal_any(boxed)


def test_unmarshal_string():
    boxed = marshal_any("foo")
    assert "type.googleapis.com/google.protobuf.StringValue" == boxed.type_url
    assert "foo" == unmarshal_any(boxed)


def test_unmarshal_bytes():
    boxed = marshal_any(b"bar")
    assert "type.googleapis.com/google.protobuf.BytesValue" == boxed.type_url
    assert b"bar" == unmarshal_any(boxed)


def test_unmarshal_timestamp():
    ts = datetime.fromtimestamp(1719372909.641448, UTC)
    boxed = marshal_any(ts)
    assert "type.googleapis.com/google.protobuf.Timestamp" == boxed.type_url
    assert ts == unmarshal_any(boxed)


def test_unmarshal_duration():
    d = timedelta(seconds=1, microseconds=1234)
    boxed = marshal_any(d)
    assert "type.googleapis.com/google.protobuf.Duration" == boxed.type_url
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


def test_unmarshal_json_like():
    value = {
        "null": None,
        "bool": True,
        "int": 11,
        "float": 3.14,
        "string": "foo",
        "list": [None, "abc", 1.23],
        "object": {"a": ["b", "c"]},
    }
    boxed = marshal_any(value)
    assert "type.googleapis.com/google.protobuf.Value" == boxed.type_url
    assert value == unmarshal_any(boxed)
