# This file is not part of the example. It is a test file to ensure the example
# works as expected during the CI process.


import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from ... import function_service
from ...test_client import ServerTest


class TestGithubStats(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {
            "DISPATCH_ENDPOINT_URL": "http://function-service",
            "DISPATCH_API_KEY": "0000000000000000",
        },
    )
    def test_foo(self):
        from . import app

        server = ServerTest()
        servicer = server.servicer
        app.dispatch._client = server.client
        app.get_repo_info._client = server.client
        app.get_contributors._client = server.client
        app.main._client = server.client

        http_client = TestClient(app.app, base_url="http://dispatch-service")
        app_client = function_service.client(http_client)

        response = http_client.get("/")
        self.assertEqual(response.status_code, 200)

        server.execute(app_client)
        server.execute(app_client)

        self.assertEqual(len(servicer.responses), 1)
