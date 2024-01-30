import unittest
import dispatch
import dispatch.fastapi
import fastapi
from fastapi.testclient import TestClient
import google.protobuf.wrappers_pb2
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

    def test_configure_no_mount_path(self):
        app = fastapi.FastAPI()
        with self.assertRaises(ValueError):
            dispatch.fastapi.configure(app, api_key="test-key", mount_path=None)

    def test_fastapi_simple_request(self):
        app = dispatch.fastapi._new_app()

        @app.dispatch_coroutine()
        def my_cool_coroutine(input):
            return f"You told me: '{input}' ({len(input)} characters)"

        http_client = TestClient(app)

        client = executor_service.client(http_client)

        input_any = google.protobuf.any_pb2.Any()
        input_any.Pack(google.protobuf.wrappers_pb2.StringValue(value="Hello World!"))
        req = ring.coroutine.v1.coroutine_pb2.ExecuteRequest(
            coroutine_uri=my_cool_coroutine.__qualname__,
            coroutine_version="1",
            input=input_any,
        )

        resp = client.Execute(req)

        self.assertIsInstance(resp, ring.coroutine.v1.coroutine_pb2.ExecuteResponse)
        self.assertEqual(resp.coroutine_uri, req.coroutine_uri)
        self.assertEqual(resp.coroutine_version, req.coroutine_version)

        resp.exit.result.output.Unpack(
            output := google.protobuf.wrappers_pb2.StringValue()
        )
        self.assertEqual(output.value, "You told me: 'Hello World!' (12 characters)")
