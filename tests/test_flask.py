import base64
import os
import pickle
import struct
import unittest
from typing import Any, Optional
from unittest import mock

import google.protobuf.any_pb2
import google.protobuf.wrappers_pb2
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from flask import Flask

import dispatch
from dispatch.experimental.durable.registry import clear_functions
from dispatch.flask import Dispatch
from dispatch.function import Arguments, Error, Function, Input, Output
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    parse_verification_key,
    private_key_from_pem,
    public_key_from_pem,
)
from dispatch.status import Status
from dispatch.test import DispatchServer, DispatchService, EndpointClient
from dispatch.test.flask import http_client


def create_dispatch_instance(app: Flask, endpoint: str):
    return Dispatch(
        app,
        endpoint=endpoint,
        api_key="0000000000000000",
        api_url="http://127.0.0.1:10000",
    )


def create_endpoint_client(app: Flask, signing_key: Optional[Ed25519PrivateKey] = None):
    return EndpointClient(http_client(app), signing_key)


class TestFlask(unittest.TestCase):
    def test_flask(self):
        app = Flask(__name__)
        dispatch = create_dispatch_instance(app, endpoint="http://127.0.0.1:9999/")

        @dispatch.primitive_function
        async def my_function(input: Input) -> Output:
            return Output.value(
                f"You told me: '{input.input}' ({len(input.input)} characters)"
            )

        client = create_endpoint_client(app)
        pickled = pickle.dumps("Hello World!")
        input_any = google.protobuf.any_pb2.Any()
        input_any.Pack(google.protobuf.wrappers_pb2.BytesValue(value=pickled))

        req = function_pb.RunRequest(
            function=my_function.name,
            input=input_any,
        )

        resp = client.run(req)

        self.assertIsInstance(resp, function_pb.RunResponse)

        resp.exit.result.output.Unpack(
            output_bytes := google.protobuf.wrappers_pb2.BytesValue()
        )
        output = pickle.loads(output_bytes.value)

        self.assertEqual(output, "You told me: 'Hello World!' (12 characters)")


signing_key = private_key_from_pem(
    """
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF
-----END PRIVATE KEY-----
"""
)

verification_key = public_key_from_pem(
    """
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=
-----END PUBLIC KEY-----
"""
)


class TestFlaskE2E(unittest.TestCase):
    def setUp(self):
        self.endpoint_app = Flask(__name__)
        endpoint_client = create_endpoint_client(self.endpoint_app, signing_key)

        api_key = "0000000000000000"
        self.dispatch_service = DispatchService(
            endpoint_client, api_key, collect_roundtrips=True
        )
        self.dispatch_server = DispatchServer(self.dispatch_service)
        self.dispatch_client = dispatch.Client(
            api_key, api_url=self.dispatch_server.url
        )

        self.dispatch = Dispatch(
            self.endpoint_app,
            endpoint="http://function-service",  # unused
            verification_key=verification_key,
            api_key=api_key,
            api_url=self.dispatch_server.url,
        )

        self.dispatch_server.start()

    def tearDown(self):
        self.dispatch_server.stop()

    def test_simple_end_to_end(self):
        # The Flask server.
        @self.dispatch.function
        def my_function(name: str) -> str:
            return f"Hello world: {name}"

        call = my_function.build_call(52)
        self.assertEqual(call.function.split(".")[-1], "my_function")

        # The client.
        [dispatch_id] = self.dispatch_client.dispatch([my_function.build_call(52)])

        # Simulate execution for testing purposes.
        self.dispatch_service.dispatch_calls()

        # Validate results.
        roundtrips = self.dispatch_service.roundtrips[dispatch_id]
        self.assertEqual(len(roundtrips), 1)
        _, response = roundtrips[0]
        self.assertEqual(any_unpickle(response.exit.result.output), "Hello world: 52")
