from fastapi import FastAPI
from fastapi.testclient import TestClient

import dispatch.test.httpx
from dispatch.test.client import HttpClient


def http_client(app: FastAPI) -> HttpClient:
    """Build a client for a FastAPI app."""
    return dispatch.test.httpx.Client(TestClient(app))
