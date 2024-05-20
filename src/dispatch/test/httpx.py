from typing import Mapping

import httpx

from dispatch.test.http import HttpClient, HttpResponse


class Client(HttpClient):
    def __init__(self, client: httpx.Client):
        self.client = client

    def get(self, url: str, headers: Mapping[str, str] = {}) -> HttpResponse:
        response = self.client.get(url, headers=headers)
        return Response(response)

    def post(
        self, url: str, body: bytes, headers: Mapping[str, str] = {}
    ) -> HttpResponse:
        response = self.client.post(url, content=body, headers=headers)
        return Response(response)

    def url_for(self, path: str) -> str:
        return str(httpx.URL(self.client.base_url).join(path))


class Response(HttpResponse):
    def __init__(self, response: httpx.Response):
        self.response = response

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def body(self):
        return self.response.content

    def raise_for_status(self):
        self.response.raise_for_status()
