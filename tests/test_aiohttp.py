import asyncio
import base64
import os
import pickle
import struct
import threading
import unittest
from typing import Any, Tuple
from unittest import mock

import fastapi
import google.protobuf.any_pb2
import google.protobuf.wrappers_pb2
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import dispatch.test.httpx
from dispatch.aiohttp import Dispatch, Server
from dispatch.asyncio import Runner
from dispatch.experimental.durable.registry import clear_functions
from dispatch.function import Arguments, Error, Function, Input, Output, Registry
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


def run(runner: Runner, server: Server, ready: threading.Event):
    try:
        with runner:
            runner.run(serve(server, ready))
    except RuntimeError as e:
        pass  # silence errors triggered by stopping the loop after tests are done


async def serve(server: Server, ready: threading.Event):
    async with server:
        ready.set()  # allow the test to continue after the server started
        await asyncio.Event().wait()


class TestAIOHTTP(unittest.TestCase):
    def setUp(self):
        ready = threading.Event()
        self.runner = Runner()

        host = "127.0.0.1"
        port = 9997

        self.endpoint = f"http://{host}:{port}"
        self.dispatch = Dispatch(
            Registry(
                endpoint=self.endpoint,
                api_key="0000000000000000",
                api_url="http://127.0.0.1:10000",
            ),
        )

        self.client = httpx.Client(timeout=1.0)
        self.server = Server(host, port, self.dispatch)
        self.thread = threading.Thread(
            target=lambda: run(self.runner, self.server, ready)
        )
        self.thread.start()
        ready.wait()

    def tearDown(self):
        loop = self.runner.get_loop()
        loop.call_soon_threadsafe(loop.stop)
        self.thread.join(timeout=1.0)
        self.client.close()

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
        async def my_function(input: Input) -> Output:
            return Output.value(
                f"You told me: '{input.input}' ({len(input.input)} characters)"
            )

        http_client = dispatch.test.httpx.Client(httpx.Client(base_url=self.endpoint))
        client = EndpointClient(http_client)

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
