import unittest
import dispatch
import dispatch.fastapi
import fastapi
from fastapi.testclient import TestClient

import ring.coroutine.v1.coroutine_pb2
from . import executor_service


class TestFastAPI(unittest.TestCase):
    def test_configure(self):
        app = fastapi.FastAPI()

        dispatch.fastapi.configure(app, api_key="test-key")

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        client = TestClient(app)

        # Ensure existing routes are still working.
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)

        # Ensure Dispatch root is working.
        resp = client.get("/dispatch/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "ok")

    def test_configure_no_app(self):
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(None, api_key="test-key")

    def test_configure_no_api_key(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key=None)

    def test_configure_no_api_url(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key="test-key", api_url=None)

    def test_configure_no_mount_path(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key="test-key", mount_path=None)

    def test_fastapi_empty_request(self):
        app = dispatch.fastapi._new_app()
        http_client = TestClient(app)

        client = executor_service.client(http_client)

        req = ring.coroutine.v1.coroutine_pb2.ExecuteRequest(
            coroutine_uri="my-cool-coroutine",
            coroutine_version="1",
        )

        resp = client.Execute(req)

        self.assertIsInstance(resp, ring.coroutine.v1.coroutine_pb2.ExecuteResponse)
        self.assertEqual(resp.coroutine_uri, req.coroutine_uri)
        self.assertEqual(resp.coroutine_version, req.coroutine_version)
