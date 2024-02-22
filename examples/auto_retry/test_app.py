# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from dispatch import Client
from dispatch.sdk.v1 import status_pb2 as status_pb
from dispatch.test import DispatchServer, DispatchService, EndpointClient


class TestAutoRetry(unittest.TestCase):
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

            # Seed(2) used in the app outputs 0, 0, 0, 2, 1, 5. So we expect 6
            # calls, including 5 retries.
            for i in range(6):
                dispatch_service.dispatch_calls()

            self.assertEqual(len(dispatch_service.roundtrips), 1)
            roundtrips = list(dispatch_service.roundtrips.values())[0]
            self.assertEqual(len(roundtrips), 6)

            statuses = [response.status for request, response in roundtrips]
            self.assertEqual(
                statuses, [status_pb.STATUS_TEMPORARY_ERROR] * 5 + [status_pb.STATUS_OK]
            )
