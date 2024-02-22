# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from dispatch import Client
from dispatch.test import DispatchServer, DispatchService, EndpointClient


class TestGettingStarted(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {
            "DISPATCH_ENDPOINT_URL": "http://function-service",
            "DISPATCH_API_KEY": "0000000000000000",
        },
    )
    def test_app(self):
        from .app import app, dispatch

        # Setup a fake Dispatch server.
        endpoint_client = EndpointClient.from_app(app)
        dispatch_service = DispatchService(endpoint_client, collect_roundtrips=True)
        with DispatchServer(dispatch_service) as dispatch_server:

            # Use it when dispatching function calls.
            dispatch.set_client(Client(api_url=dispatch_server.url))

            http_client = TestClient(app)
            response = http_client.get("/")
            self.assertEqual(response.status_code, 200)

            dispatch_service.dispatch_calls()

            self.assertEqual(len(dispatch_service.roundtrips), 1)  # one call submitted
            dispatch_id, roundtrips = list(dispatch_service.roundtrips.items())[0]
            self.assertEqual(len(roundtrips), 1)  # one roundtrip for this call
