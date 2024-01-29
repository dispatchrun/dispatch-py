import unittest
import dispatch
import fastapi
from fastapi.testclient import TestClient


class TestFastapi(unittest.TestCase):
    def test_fastapi(self):
        app = fastapi.FastAPI()

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        client = TestClient(app)
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
