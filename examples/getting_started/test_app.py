# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from dispatch import Client
from dispatch.test import DispatchServer, EndpointClient

from ...dispatch_service import MockDispatchService


class TestGettingStarted(unittest.TestCase):
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
        app.publish._client = dispatch_client

        http_client = TestClient(app.app)
        response = http_client.get("/")
        self.assertEqual(response.status_code, 200)

        dispatch_service.dispatch_calls()
        self.assertEqual(len(dispatch_service.responses), 1)
