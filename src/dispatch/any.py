from __future__ import annotations

import pickle
from datetime import UTC, datetime, timedelta
from typing import Any

import google.protobuf.any_pb2
import google.protobuf.duration_pb2
import google.protobuf.empty_pb2
import google.protobuf.message
import google.protobuf.timestamp_pb2
import google.protobuf.wrappers_pb2
from google.protobuf import descriptor_pool, message_factory

from dispatch.sdk.python.v1 import pickled_pb2 as pickled_pb

INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807


def marshal_any(value: Any) -> google.protobuf.any_pb2.Any:
    if value is None:
        value = google.protobuf.empty_pb2.Empty()
    elif isinstance(value, bool):
        value = google.protobuf.wrappers_pb2.BoolValue(value=value)
    elif isinstance(value, int) and INT64_MIN <= value <= INT64_MAX:
        # To keep things simple, serialize all integers as int64 on the wire.
        # For larger integers, fall through and use pickle.
        value = google.protobuf.wrappers_pb2.Int64Value(value=value)
    elif isinstance(value, float):
        value = google.protobuf.wrappers_pb2.DoubleValue(value=value)
    elif isinstance(value, str):
        value = google.protobuf.wrappers_pb2.StringValue(value=value)
    elif isinstance(value, bytes):
        value = google.protobuf.wrappers_pb2.BytesValue(value=value)
    elif isinstance(value, datetime):
        # Note: datetime only supports microsecond granularity
        seconds = int(value.timestamp())
        nanos = value.microsecond * 1000
        value = google.protobuf.timestamp_pb2.Timestamp(seconds=seconds, nanos=nanos)
    elif isinstance(value, timedelta):
        # Note: timedelta only supports microsecond granularity
        seconds = int(value.total_seconds())
        nanos = value.microseconds * 1000
        value = google.protobuf.duration_pb2.Duration(seconds=seconds, nanos=nanos)

    if not isinstance(value, google.protobuf.message.Message):
        value = pickled_pb.Pickled(pickled_value=pickle.dumps(value))

    any = google.protobuf.any_pb2.Any()
    if value.DESCRIPTOR.full_name.startswith("dispatch.sdk."):
        any.Pack(value, type_url_prefix="buf.build/stealthrocket/dispatch-proto/")
    else:
        any.Pack(value)

    return any


def unmarshal_any(any: google.protobuf.any_pb2.Any) -> Any:
    pool = descriptor_pool.Default()
    msg_descriptor = pool.FindMessageTypeByName(any.TypeName())
    proto = message_factory.GetMessageClass(msg_descriptor)()
    any.Unpack(proto)

    if isinstance(proto, pickled_pb.Pickled):
        return pickle.loads(proto.pickled_value)
    elif isinstance(proto, google.protobuf.empty_pb2.Empty):
        return None
    elif isinstance(proto, google.protobuf.wrappers_pb2.BoolValue):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.Int32Value):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.Int64Value):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.UInt32Value):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.UInt64Value):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.FloatValue):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.DoubleValue):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.StringValue):
        return proto.value
    elif isinstance(proto, google.protobuf.wrappers_pb2.BytesValue):
        try:
            # Assume it's the legacy container for pickled values.
            return pickle.loads(proto.value)
        except Exception as e:
            # Otherwise, return the literal bytes.
            return proto.value
    elif isinstance(proto, google.protobuf.timestamp_pb2.Timestamp):
        return proto.ToDatetime(tzinfo=UTC)
    elif isinstance(proto, google.protobuf.duration_pb2.Duration):
        return proto.ToTimedelta()

    return proto
