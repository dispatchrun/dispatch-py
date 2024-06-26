from __future__ import annotations

import pickle
from typing import Any

import google.protobuf.any_pb2
import google.protobuf.message
import google.protobuf.wrappers_pb2
from google.protobuf import descriptor_pool, message_factory

from dispatch.sdk.python.v1 import pickled_pb2 as pickled_pb


def marshal_any(value: Any) -> google.protobuf.any_pb2.Any:
    any = google.protobuf.any_pb2.Any()
    if isinstance(value, google.protobuf.message.Message):
        any.Pack(value)
    else:
        p = pickled_pb.Pickled(pickled_value=pickle.dumps(value))
        any.Pack(p, type_url_prefix="buf.build/stealthrocket/dispatch-proto/")
    return any


def unmarshal_any(any: google.protobuf.any_pb2.Any) -> Any:
    if any.Is(pickled_pb.Pickled.DESCRIPTOR):
        p = pickled_pb.Pickled()
        any.Unpack(p)
        return pickle.loads(p.pickled_value)

    elif any.Is(google.protobuf.wrappers_pb2.BytesValue.DESCRIPTOR):
        b = google.protobuf.wrappers_pb2.BytesValue()
        any.Unpack(b)
        try:
            # Assume it's the legacy container for pickled values.
            return pickle.loads(b.value)
        except Exception as e:
            # Otherwise, return the literal bytes.
            return b.value

    pool = descriptor_pool.Default()
    msg_descriptor = pool.FindMessageTypeByName(any.TypeName())
    proto = message_factory.GetMessageClass(msg_descriptor)()
    any.Unpack(proto)
    return proto
