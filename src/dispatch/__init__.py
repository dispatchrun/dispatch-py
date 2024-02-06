"""The Dispatch SDK for Python.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import TypeAlias
from urllib.parse import urlparse

import grpc

import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
from dispatch.function import Call

__all__ = ["Client", "DispatchID", "Call"]


DispatchID: TypeAlias = str
"""Unique identifier in Dispatch.

It should be treated as an opaque value.
"""


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

        self._stub = dispatch_grpc.DispatchServiceStub(channel)

    def dispatch(self, calls: Iterable[Call]) -> Iterable[DispatchID]:
        """Dispatch function calls.

        Returns:
            Identifiers for the function calls, in the same order as the inputs.
        """
        req = dispatch_pb.DispatchRequest(calls=[c._as_proto() for c in calls])
        resp = self._stub.Dispatch(req)
        return [DispatchID(x) for x in resp.dispatch_ids]
