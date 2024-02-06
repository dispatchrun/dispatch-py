"""The Dispatch SDK for Python.
"""

from __future__ import annotations

import os
import pickle
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, TypeAlias
from urllib.parse import urlparse

import google.protobuf
import google.protobuf.any_pb2
import google.protobuf.message
import google.protobuf.wrappers_pb2
import grpc

import dispatch.coroutine
import dispatch.sdk.v1.endpoint_pb2 as endpoint_pb
import dispatch.sdk.v1.endpoint_pb2_grpc as endpoint_grpc

__all__ = ["Client", "ExecutionID", "ExecutionInput", "ExecutionDef"]

__version__ = "0.0.1"


ExecutionID: TypeAlias = str
"""Unique execution identifier in Dispatch.

It should be treated as an opaque value.
"""


@dataclass(frozen=True)
class ExecutionInput:
    """Definition of an execution to be created on Dispatch.

    Attributes:
        coroutine_uri: The URI of the coroutine to execute.
        input: The input to pass to the coroutine. If the input is a protobuf
          message, it will be wrapped in a google.protobuf.Any message. If the
          input is not a protobuf message, it will be pickled and wrapped in a
          google.protobuf.Any message.
    """

    coroutine_uri: str
    input: Any


ExecutionDef: TypeAlias = ExecutionInput | dispatch.coroutine.Call
"""Definition of an execution to be ran on Dispatch.

Can be either an ExecutionInput or a Call. ExecutionInput can be created
manually, likely to call a coroutine outside the current code base. Call is
created by the `dispatch.coroutine` module and is used to call a coroutine
defined in the current code base.
"""


def _executiondef_to_proto(execdef: ExecutionDef) -> endpoint_pb.Execution:
    input = execdef.input
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
    return endpoint_pb.Execution(coroutine_uri=execdef.coroutine_uri, input=input_any)


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

    def execute(self, executions: Iterable[ExecutionDef]) -> Iterable[ExecutionID]:
        """Execute on Dispatch using the provided inputs.

        Returns:
            The ID of the created executions, in the same order as the inputs.
        """
        req = endpoint_pb.CreateExecutionsRequest()
        for e in executions:
            req.executions.append(_executiondef_to_proto(e))
        resp = self._stub.CreateExecutions(req)
        return [ExecutionID(x) for x in resp.ids]
