import base64
import os
import pickle
import struct
import threading
import unittest
from http.server import HTTPServer
from typing import Any
from unittest import mock

import fastapi
import google.protobuf.any_pb2
import google.protobuf.wrappers_pb2
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dispatch.experimental.durable.registry import clear_functions
from dispatch.function import Arguments, Error, Function, Input, Output, Registry
from dispatch.http import Dispatch
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import parse_verification_key, public_key_from_pem
from dispatch.status import Status
from dispatch.test import EndpointClient

public_key_pem = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=\n-----END PUBLIC KEY-----"
public_key_pem2 = "-----BEGIN PUBLIC KEY-----\\nMCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=\\n-----END PUBLIC KEY-----"
public_key = public_key_from_pem(public_key_pem)
public_key_bytes = public_key.public_bytes_raw()
public_key_b64 = base64.b64encode(public_key_bytes)

from datetime import datetime


def create_dispatch_instance(endpoint: str):
    return Dispatch(
        Registry(
            endpoint=endpoint,
            api_key="0000000000000000",
            api_url="http://127.0.0.1:10000",
        ),
    )


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.server_address = ("127.0.0.1", 9999)
        self.endpoint = f"http://{self.server_address[0]}:{self.server_address[1]}"
        self.dispatch = create_dispatch_instance(self.endpoint)
        self.client = httpx.Client(timeout=1.0)
        self.server = HTTPServer(self.server_address, self.dispatch)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.05)
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=1.0)
        self.client.close()
        self.server.server_close()

    def test_content_length_missing(self):
        resp = self.client.post(f"{self.endpoint}/dispatch.sdk.v1.FunctionService/Run")
        body = resp.read()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            body, b'{"code":"invalid_argument","message":"content length is required"}'
        )

    def test_content_length_too_large(self):
        resp = self.client.post(
            f"{self.endpoint}/dispatch.sdk.v1.FunctionService/Run",
            data={"msg": "a" * 16_000_001},
        )
        body = resp.read()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            body, b'{"code":"invalid_argument","message":"content length is too large"}'
        )

    def test_simple_request(self):
        @self.dispatch.registry.primitive_function
        def my_function(input: Input) -> Output:
            return Output.value(
                f"You told me: '{input.input}' ({len(input.input)} characters)"
            )

        client = EndpointClient.from_url(self.endpoint)

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
