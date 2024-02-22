import unittest

import fastapi
import httpx

import dispatch
from dispatch.fastapi import Dispatch
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.signature import private_key_from_pem, public_key_from_pem
from dispatch.test import DispatchServer, DispatchService, EndpointClient

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


class TestFullFastapi(unittest.TestCase):
    def setUp(self):
        self.endpoint_app = fastapi.FastAPI()
        endpoint_client = EndpointClient.from_app(self.endpoint_app, signing_key)

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
        # The FastAPI server.
        @self.dispatch.function
        def my_function(name: str) -> str:
            return f"Hello world: {name}"

        # The client.
        [dispatch_id] = self.dispatch_client.dispatch([my_function.build_call(52)])

        # Simulate execution for testing purposes.
        self.dispatch_service.dispatch_calls()

        # Validate results.
        roundtrips = self.dispatch_service.roundtrips[dispatch_id]
        self.assertEqual(len(roundtrips), 1)
        _, response = roundtrips[0]
        self.assertEqual(any_unpickle(response.exit.result.output), "Hello world: 52")

    def test_simple_missing_signature(self):
        @self.dispatch.function
        def my_function(name: str) -> str:
            return f"Hello world: {name}"

        [dispatch_id] = self.dispatch_client.dispatch([my_function.build_call(52)])

        self.dispatch_service.endpoint_client = EndpointClient.from_app(
            self.endpoint_app
        )  # no signing key
        try:
            self.dispatch_service.dispatch_calls()
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 403
            assert e.response.json() == {
                "code": "permission_denied",
                "message": 'Expected "Signature-Input" header field to be present',
            }
        else:
            assert False, "Expected HTTPStatusError"
