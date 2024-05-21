from typing import Mapping

import werkzeug.test
from flask import Flask

from dispatch.test.http import HttpClient, HttpResponse


def http_client(app: Flask) -> HttpClient:
    """Build a client for a Flask app."""
    return Client(app.test_client())


class Client(HttpClient):
    def __init__(self, client: werkzeug.test.Client):
        self.client = client

    def get(self, url: str, headers: Mapping[str, str] = {}) -> HttpResponse:
        response = self.client.get(url, headers=headers.items())
        return Response(response)

    def post(
        self, url: str, body: bytes, headers: Mapping[str, str] = {}
    ) -> HttpResponse:
        response = self.client.post(url, data=body, headers=headers.items())
        return Response(response)

    def url_for(self, path: str) -> str:
        return "http://localhost" + path


class Response(HttpResponse):
    def __init__(self, response):
        self.response = response

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def body(self):
        return self.response.data

    def raise_for_status(self):
        if self.response.status_code // 100 != 2:
            raise RuntimeError(f"HTTP status code {self.response.status_code}")
