import unittest
import dispatch
import dispatch.fastapi
import fastapi
from fastapi.testclient import TestClient


class TestFastAPI(unittest.TestCase):
    def test_fastapi(self):
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
