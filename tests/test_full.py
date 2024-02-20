import unittest

import fastapi
import httpx
from fastapi.testclient import TestClient

from dispatch import Call, Input, Output
from dispatch.fastapi import Dispatch
from dispatch.proto import _any_unpickle as any_unpickle
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
        self.dispatch = Dispatch(
            self.app,
            endpoint="http://function-service",
            verification_key=public_key,
            api_key="0000000000000000",
            api_url="http://127.0.0.1:10000",
        )

        self.http_client = TestClient(self.app, base_url="http://dispatch-service")
        self.app_client = function_service.client(
            self.http_client, signing_key=private_key
        )

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
        @self.dispatch.function
        def my_function(name: str) -> str:
            return f"Hello world: {name}"

        # The client.
        [dispatch_id] = self.client.dispatch([my_function.build_call(52)])

        # Simulate execution for testing purposes.
        self.execute()

        # Validate results.
        resp = self.servicer.response_for(dispatch_id)
        self.assertEqual(any_unpickle(resp.exit.result.output), "Hello world: 52")

    def test_simple_missing_signature(self):
        @self.dispatch.function
        def my_function(name: str) -> str:
            return f"Hello world: {name}"

        [dispatch_id] = self.client.dispatch([my_function.build_call(52)])

        self.app_client = function_service.client(self.http_client)  # no signing key
        try:
            self.execute()
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 403
            assert e.response.json() == {
                "code": "permission_denied",
                "message": 'Expected "Signature-Input" header field to be present',
            }
        else:
            assert False, "Expected HTTPStatusError"
