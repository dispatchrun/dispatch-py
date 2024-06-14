# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from dispatch import Client
from dispatch.test import DispatchServer, DispatchService, EndpointClient
from dispatch.test.fastapi import http_client


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
        app_client = http_client(app)
        endpoint_client = EndpointClient(app_client)
        dispatch_service = DispatchService(endpoint_client, collect_roundtrips=True)
        with DispatchServer(dispatch_service) as dispatch_server:
            # Use it when dispatching function calls.
            dispatch.registry.client = Client(api_url=dispatch_server.url)

            response = app_client.get("/")
            self.assertEqual(response.status_code, 200)

            dispatch_service.dispatch_calls()

            self.assertEqual(len(dispatch_service.roundtrips), 1)  # one call submitted
            dispatch_id, roundtrips = list(dispatch_service.roundtrips.items())[0]
            self.assertEqual(len(roundtrips), 1)  # one roundtrip for this call
