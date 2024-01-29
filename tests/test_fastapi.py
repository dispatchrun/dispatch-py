import unittest
import dispatch
import dispatch.fastapi
import fastapi
from fastapi.testclient import TestClient


class TestFastAPI(unittest.TestCase):
    def test_fastapi(self):
        app = fastapi.FastAPI()

        dispatch.fastapi.configure(app)

        @app.get("/")
        def read_root():
            return {"Hello": "World"}

        client = TestClient(app)
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
