# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from dispatch.function import Client
from dispatch.test import DispatchServer, DispatchService, EndpointClient


class TestGithubStats(unittest.TestCase):
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
        endpoint_client = EndpointClient(TestClient(app))
        dispatch_service = DispatchService(endpoint_client, collect_roundtrips=True)
        with DispatchServer(dispatch_service) as dispatch_server:
            # Use it when dispatching function calls.
            dispatch.set_client(Client(api_url=dispatch_server.url))

            http_client = TestClient(app)
            response = http_client.get("/")
            self.assertEqual(response.status_code, 200)

            while dispatch_service.queue:
                dispatch_service.dispatch_calls()

            # Three unique functions were called, with five total round-trips.
            # The main function is called initially, and then polls
            # twice, for three total round-trips. There's one round-trip
            # to get_repo_info and one round-trip to get_contributors.
            self.assertEqual(
                3, len(dispatch_service.roundtrips)
            )  # 3 unique functions were called
            self.assertEqual(
                5,
                sum(
                    len(roundtrips)
                    for roundtrips in dispatch_service.roundtrips.values()
                ),
            )
