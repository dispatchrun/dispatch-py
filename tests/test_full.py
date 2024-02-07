import unittest

import fastapi
from fastapi.testclient import TestClient

import dispatch.fastapi
from dispatch import Call
from dispatch.function import Input, Output
from dispatch.function import _any_unpickle as any_unpickle
from dispatch.signature import private_key_from_pem, public_key_from_pem

from . import function_service
from .test_client import ServerTest

public_key = public_key_from_pem(
    """
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=
-----END PUBLIC KEY-----
"""
)

private_key = private_key_from_pem(
    """
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF
-----END PRIVATE KEY-----
"""
)


class TestFullFastapi(unittest.TestCase):
    def setUp(self):
        self.app = fastapi.FastAPI()
        dispatch.fastapi.configure(
            self.app, public_url="http://dispatch-service", verification_key=public_key
        )

        http_client = TestClient(self.app, base_url="http://function-service")
        self.app_client = function_service.client(http_client, signing_key=private_key)

        self.server = ServerTest()
        # shortcuts
        self.client = self.server.client
        self.servicer = self.server.servicer

    def tearDown(self):
        self.server.stop()

    def execute(self):
        self.server.execute(self.app_client)

    def test_simple_end_to_end(self):
        # The FastAPI server.
        @self.app.dispatch_function()
        def my_function(input: Input) -> Output:
            return Output.value(f"Hello world: {input.input}")

        # The client.
        [dispatch_id] = self.client.dispatch(
            [Call(function=my_function.name, input=52)]
        )

        # Simulate execution for testing purposes.
        self.execute()

        # Validate results.
        resp = self.servicer.responses[dispatch_id]
        self.assertEqual(any_unpickle(resp.exit.result.output), "Hello world: 52")

    def test_simple_call_with(self):
        @self.app.dispatch_function()
        def my_function(input: Input) -> Output:
            return Output.value(f"Hello world: {input.input}")

        [dispatch_id] = self.client.dispatch([my_function.call_with(52)])
        self.execute()
        resp = self.servicer.responses[dispatch_id]
        self.assertEqual(any_unpickle(resp.exit.result.output), "Hello world: 52")
