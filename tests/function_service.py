from datetime import datetime

import grpc
import httpx

from dispatch.sdk.v1 import function_pb2_grpc as function_grpc
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PrivateKey,
    Request,
    sign_request,
)

# This file provides a grpc client that can talk to the FunctionService
# interface. This is achieved by implementing the bare minimum of the
# grpc.Channel using httpx to make the requests, which allows us to use the
# same httpx client as the FastAPI testing framework.
#
# See test_fastapi.py for an example of how to use this client.


class UnaryUnaryMultiCallable(grpc.UnaryUnaryMultiCallable):
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
        """Synchronously invokes the underlying RPC.

        Args:
          request: The request value for the RPC.
          timeout: An optional duration of time in seconds to allow
            for the RPC.
          metadata: Optional :term:`metadata` to be transmitted to the
            service-side of the RPC.
          credentials: An optional CallCredentials for the RPC. Only valid for
            secure Channel.
          wait_for_ready: An optional flag to enable :term:`wait_for_ready` mechanism.
          compression: An element of grpc.compression, e.g.
            grpc.compression.Gzip.

        Returns:
          The response value for the RPC.

        Raises:
          RpcError: Indicating that the RPC terminated with non-OK status. The
            raised RpcError will also be a Call for the RPC affording the RPC's
            metadata, status code, and details.
        """
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


class HttpxGrpcChannel(grpc.Channel):
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
        """Creates a UnaryUnaryMultiCallable for a unary-unary method.

        Args:
          method: The name of the RPC method.
          request_serializer: Optional :term:`serializer` for serializing the request
            message. Request goes unserialized in case None is passed.
          response_deserializer: Optional :term:`deserializer` for deserializing the
            response message. Response goes undeserialized in case None
            is passed.
          signing_key: Optional Ed25519 private key to use to sign requests.

        Returns:
          A UnaryUnaryMultiCallable value for the named unary-unary method.
        """
        return UnaryUnaryMultiCallable(
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


def client(
    http_client: httpx.Client, signing_key: Ed25519PrivateKey | None = None
) -> function_grpc.FunctionServiceStub:
    channel = HttpxGrpcChannel(http_client, signing_key=signing_key)
    return function_grpc.FunctionServiceStub(channel)
