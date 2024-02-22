# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from dispatch import Client
from dispatch.sdk.v1 import status_pb2 as status_pb
from dispatch.test import DispatchServer, EndpointClient

from ...dispatch_service import MockDispatchService


class TestAutoRetry(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {
            "DISPATCH_ENDPOINT_URL": "http://function-service",
            "DISPATCH_API_KEY": "0000000000000000",
        },
    )
    def test_app(self):
        from . import app

        endpoint_client = EndpointClient.from_app(app.app)

        dispatch_service = MockDispatchService(endpoint_client)
        dispatch_server = DispatchServer(dispatch_service)
        dispatch_client = Client(api_url=dispatch_server.url)

        app.dispatch._client = dispatch_client
        app.some_logic._client = dispatch_client

        http_client = TestClient(app.app)
        response = http_client.get("/")
        self.assertEqual(response.status_code, 200)

        dispatch_service.dispatch_calls()

        # Seed(2) used in the app outputs 0, 0, 0, 2, 1, 5. So we expect 6
        # calls, including 5 retries.
        for i in range(6):
            dispatch_service.dispatch_calls()
        self.assertEqual(len(dispatch_service.responses), 6)

        statuses = [r.status for r in dispatch_service.responses.values()]
        self.assertEqual(
            statuses, [status_pb.STATUS_TEMPORARY_ERROR] * 5 + [status_pb.STATUS_OK]
        )
