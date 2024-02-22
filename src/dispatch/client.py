from __future__ import annotations

import logging
import os
from typing import Iterable
from urllib.parse import urlparse

import grpc

import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
from dispatch.id import DispatchID
from dispatch.proto import Call

logger = logging.getLogger(__name__)


DEFAULT_API_URL = "https://api.stealthrocket.cloud"


class Client:
    """Client for the Dispatch API."""

    __slots__ = ("api_url", "api_key", "_stub", "api_key_from")

    def __init__(self, api_key: None | str = None, api_url: None | str = None):
        """Create a new Dispatch client.

        Args:
            api_key: Dispatch API key to use for authentication. Uses the value of
                the DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use. Uses the value of the
                DISPATCH_API_URL environment variable if set, otherwise
                defaults to the public Dispatch API (DEFAULT_API_URL).

        Raises:
            ValueError: if the API key is missing.
        """

        if api_key:
            self.api_key_from = "api_key"
        else:
            self.api_key_from = "DISPATCH_API_KEY"
            api_key = os.environ.get("DISPATCH_API_KEY")
        if not api_key:
            raise ValueError(
                "missing API key: set it with the DISPATCH_API_KEY environment variable"
            )

        if not api_url:
            api_url = os.environ.get("DISPATCH_API_URL", DEFAULT_API_URL)
        if not api_url:
            raise ValueError(
                "missing API URL: set it with the DISPATCH_API_URL environment variable"
            )

        logger.debug("initializing client for Dispatch API at URL %s", api_url)
        self.api_url = api_url
        self.api_key = api_key
        self._init_stub()

    def __getstate__(self):
        return {"api_url": self.api_url, "api_key": self.api_key}

    def __setstate__(self, state):
        self.api_url = state["api_url"]
        self.api_key = state["api_key"]
        self._init_stub()

    def _init_stub(self):
        result = urlparse(self.api_url)
        match result.scheme:
            case "http":
                creds = grpc.local_channel_credentials()
            case "https":
                creds = grpc.ssl_channel_credentials()
            case _:
                raise ValueError(f"Invalid API scheme: '{result.scheme}'")

        call_creds = grpc.access_token_call_credentials(self.api_key)
        creds = grpc.composite_channel_credentials(creds, call_creds)
        channel = grpc.secure_channel(result.netloc, creds)

        self._stub = dispatch_grpc.DispatchServiceStub(channel)

    def dispatch(self, calls: Iterable[Call]) -> list[DispatchID]:
        """Dispatch function calls.

        Args:
            calls: Calls to dispatch.

        Returns:
            Identifiers for the function calls, in the same order as the inputs.
        """
        calls_proto = [c._as_proto() for c in calls]
        logger.debug("dispatching %d function call(s)", len(calls_proto))
        req = dispatch_pb.DispatchRequest(calls=calls_proto)

        try:
            resp = self._stub.Dispatch(req)
        except grpc.RpcError as e:
            status_code = e.code()
            match status_code:
                case grpc.StatusCode.UNAUTHENTICATED:
                    raise PermissionError(
                        f"Dispatch received an invalid authentication token (check {self.api_key_from} is correct)"
                    ) from e
            raise

        dispatch_ids = [DispatchID(x) for x in resp.dispatch_ids]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "dispatched %d function call(s): %s",
                len(calls_proto),
                ", ".join(dispatch_ids),
            )
        return dispatch_ids
