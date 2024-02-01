"""The Dispatch SDK for Python.
"""

from __future__ import annotations
import pickle
import os
from urllib.parse import urlparse
from functools import cached_property
from collections.abc import Iterable
from typing import Any, TypeAlias
from dataclasses import dataclass

import grpc
import google.protobuf

import ring.record.v1.record_pb2 as record_pb
import ring.task.v1.service_pb2 as service
import ring.task.v1.service_pb2_grpc as service_grpc
import dispatch.coroutine


__all__ = ["Client", "TaskID", "TaskInput", "TaskDef"]


@dataclass(frozen=True, repr=False)
class TaskID:
    """Unique task identifier in Dispatch.

    It should be treated as an opaque value.
    """

    partition_number: int
    block_id: int
    record_offset: int
    record_size: int

    @classmethod
    def _from_proto(cls, proto: record_pb.ID) -> TaskID:
        return cls(
            partition_number=proto.partition_number,
            block_id=proto.block_id,
            record_offset=proto.record_offset,
            record_size=proto.record_size,
        )

    def _to_proto(self) -> record_pb.ID:
        return record_pb.ID(
            partition_number=self.partition_number,
            block_id=self.block_id,
            record_offset=self.record_offset,
            record_size=self.record_size,
        )

    def __str__(self) -> str:
        parts = [
            self.partition_number,
            self.block_id,
            self.record_offset,
            self.record_size,
        ]
        return "".join("{:08x}".format(a) for a in parts)

    def __repr__(self) -> str:
        return f"TaskID({self})"


@dataclass(frozen=True)
class TaskInput:
    """Definition of a task to be created on Dispatch.

    Attributes:
        coroutine_uri: The URI of the coroutine to execute.
        input: The input to pass to the coroutine. If the input is a protobuf
            message, it will be wrapped in a google.protobuf.Any message. If the
            input is not a protobuf message, it will be pickled and wrapped in a
            google.protobuf.Any message.
    """

    coroutine_uri: str
    input: Any


TaskDef: TypeAlias = TaskInput | dispatch.coroutine.Call
"""Definition of a task to be created on Dispatch.

Can be either a TaskInput or a Call. TaskInput can be created manually, likely
to call a coroutine outside the current code base. Call is created by the
`dispatch.coroutine` module and is used to call a coroutine defined in the
current code base.
"""


def _taskdef_to_proto(taskdef: TaskDef) -> service.CreateTaskInput:
    input = taskdef.input
    match input:
        case google.protobuf.any_pb2.Any():
            input_any = input
        case google.protobuf.message.Message():
            input_any = google.protobuf.any_pb2.Any()
            input_any.Pack(input)
        case _:
            pickled = pickle.dumps(input)
            input_any = google.protobuf.any_pb2.Any()
            input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=pickled))
    return service.CreateTaskInput(coroutine_uri=taskdef.coroutine_uri, input=input_any)


class Client:
    """Client for the Dispatch API."""

    def __init__(
        self, api_key: None | str = None, api_url="https://api.stealthrocket.cloud"
    ):
        """Create a new Dispatch client.

        Args:
            api_key: Dispatch API key to use for authentication. Uses the value of
              the DISPATCH_API_KEY environment variable by default.
            api_url: The URL of the Dispatch API to use. Defaults to the public
                Dispatch API.

        Raises:
            ValueError: if the API key is missing.
        """
        if not api_key:
            api_key = os.environ.get("DISPATCH_API_KEY")
        if not api_key:
            raise ValueError("api_key is required")

        result = urlparse(api_url)
        match result.scheme:
            case "http":
                creds = grpc.local_channel_credentials()
            case "https":
                creds = grpc.ssl_channel_credentials()
            case _:
                raise ValueError(f"Invalid API scheme: '{result.scheme}'")

        call_creds = grpc.access_token_call_credentials(api_key)
        creds = grpc.composite_channel_credentials(creds, call_creds)
        channel = grpc.secure_channel(result.netloc, creds)

        self._stub = service_grpc.ServiceStub(channel)

    def create_tasks(self, tasks: Iterable[TaskDef]) -> Iterable[TaskID]:
        """Create tasks on Dispatch using the provided inputs.

        Returns:
            The ID of the created tasks, in the same order as the inputs.
        """
        req = service.CreateTasksRequest()
        for task in tasks:
            req.tasks.append(_taskdef_to_proto(task))
        resp = self._stub.CreateTasks(req)
        return [TaskID._from_proto(x.id) for x in resp.tasks]
