from datetime import datetime

import fastapi
import grpc
import httpx
from fastapi.testclient import TestClient

from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.sdk.v1 import function_pb2_grpc as function_grpc
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PrivateKey,
    Request,
    sign_request,
)


class EndpointClient:
    """Test client for a Dispatch programmable endpoint.

    Note that this is different from dispatch.Client, which is a client
    for the Dispatch API. The EndpointClient is a client similar to the one
    that Dispatch itself would use to interact with an endpoint that provides
    functions, for example a FastAPI app.
    """

    def __init__(
        self, http_client: httpx.Client, signing_key: Ed25519PrivateKey | None = None
    ):
        """Initialize the client.

        Args:
            http_client: Client to use to make HTTP requests.
            signing_key: Optional Ed25519 private key to use to sign requests.
        """
        channel = _HttpxGrpcChannel(http_client, signing_key=signing_key)
        self._stub = function_grpc.FunctionServiceStub(channel)

    def run(self, request: function_pb.RunRequest) -> function_pb.RunResponse:
        """Send a run request to an endpoint and return its response.

        Args:
            request: A FunctionService Run request.

        Returns:
            RunResponse: the response from the endpoint.
        """
        return self._stub.Run(request)

    @classmethod
    def from_url(cls, url: str, signing_key: Ed25519PrivateKey | None = None):
        """Returns an EndpointClient for a Dispatch endpoint URL."""
        http_client = httpx.Client(base_url=url)
        return EndpointClient(http_client, signing_key)

    @classmethod
    def from_app(
        cls, app: fastapi.FastAPI, signing_key: Ed25519PrivateKey | None = None
    ):
        """Returns an EndpointClient for a Dispatch endpoint bound to a
        FastAPI app instance."""
        http_client = TestClient(app)
        return EndpointClient(http_client, signing_key)


class _HttpxGrpcChannel(grpc.Channel):
    def __init__(
        self, http_client: httpx.Client, signing_key: Ed25519PrivateKey | None = None
    ):
        self.http_client = http_client
        self.signing_key = signing_key

    def subscribe(self, callback, try_to_connect=False):
        raise NotImplementedError()

    def unsubscribe(self, callback):
        raise NotImplementedError()

    def unary_unary(self, method, request_serializer=None, response_deserializer=None):
        return _UnaryUnaryMultiCallable(
            self.http_client,
            method,
            request_serializer,
            response_deserializer,
            self.signing_key,
        )

    def unary_stream(self, method, request_serializer=None, response_deserializer=None):
        raise NotImplementedError()

    def stream_unary(self, method, request_serializer=None, response_deserializer=None):
        raise NotImplementedError()

    def stream_stream(
        self, method, request_serializer=None, response_deserializer=None
    ):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def __enter__(self):
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError()


class _UnaryUnaryMultiCallable(grpc.UnaryUnaryMultiCallable):
    def __init__(
        self,
        client,
        method,
        request_serializer,
        response_deserializer,
        signing_key: Ed25519PrivateKey | None = None,
    ):
        self.client = client
        self.method = method
        self.request_serializer = request_serializer
        self.response_deserializer = response_deserializer
        self.signing_key = signing_key

    def __call__(
        self,
        request,
        timeout=None,
        metadata=None,
        credentials=None,
        wait_for_ready=None,
        compression=None,
    ):
        request = Request(
            method="POST",
            url=str(httpx.URL(self.client.base_url).join(self.method)),
            body=self.request_serializer(request),
            headers=CaseInsensitiveDict({"Content-Type": "application/grpc+proto"}),
        )

        if self.signing_key is not None:
            sign_request(request, self.signing_key, datetime.now())

        response = self.client.post(
            request.url, content=request.body, headers=request.headers
        )
        response.raise_for_status()
        return self.response_deserializer(response.content)

    def with_call(
        self,
        request,
        timeout=None,
        metadata=None,
        credentials=None,
        wait_for_ready=None,
        compression=None,
    ):
        raise NotImplementedError()

    def future(
        self,
        request,
        timeout=None,
        metadata=None,
        credentials=None,
        wait_for_ready=None,
        compression=None,
    ):
        raise NotImplementedError()
