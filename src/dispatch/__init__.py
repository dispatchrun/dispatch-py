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

import dispatch.sdk.v1.endpoint_pb2 as endpoint_pb
import dispatch.sdk.v1.endpoint_pb2_grpc as endpoint_grpc
import dispatch.coroutine


__all__ = ["Client", "TaskID", "TaskInput", "TaskDef"]


TaskID: TypeAlias = str
"""Unique task identifier in Dispatch.

It should be treated as an opaque value.
"""


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


def _taskdef_to_proto(taskdef: TaskDef) -> endpoint_pb.Execution:
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
    return endpoint_pb.Execution(coroutine_uri=taskdef.coroutine_uri, input=input_any)


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

        self._stub = endpoint_grpc.EndpointServiceStub(channel)

    def create_tasks(self, tasks: Iterable[TaskDef]) -> Iterable[TaskID]:
        """Create tasks on Dispatch using the provided inputs.

        Returns:
            The ID of the created tasks, in the same order as the inputs.
        """
        req = endpoint_pb.CreateExecutionsRequest()
        for task in tasks:
            req.executions.append(_taskdef_to_proto(task))
        resp = self._stub.CreateExecutions(req)
        return [TaskID(x) for x in resp.ids]
