import asyncio
import socket
import sys

import fastapi
import google.protobuf.any_pb2
import google.protobuf.wrappers_pb2
import httpx
import uvicorn
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dispatch
from dispatch.asyncio import Runner
from dispatch.experimental.durable.registry import clear_functions
from dispatch.fastapi import Dispatch
from dispatch.function import Arguments, Client, Error, Input, Output, Registry
from dispatch.sdk.v1 import call_pb2 as call_pb
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    parse_verification_key,
    private_key_from_pem,
    public_key_from_pem,
)
from dispatch.status import Status


class TestFastAPI(dispatch.test.TestCase):

    def dispatch_test_init(self, reg: Registry) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)

        (host, port) = sock.getsockname()

        app = FastAPI()
        dispatch = Dispatch(app, registry=reg)

        config = uvicorn.Config(app, host=host, port=port)
        self.sockets = [sock]
        self.uvicorn = uvicorn.Server(config)
        self.runner = Runner()
        if sys.version_info >= (3, 10):
            self.event = asyncio.Event()
        else:
            self.event = asyncio.Event(loop=self.runner.get_loop())
        return f"http://{host}:{port}"

    def dispatch_test_run(self):
        loop = self.runner.get_loop()
        loop.create_task(self.uvicorn.serve(self.sockets))
        self.runner.run(self.event.wait())
        self.runner.close()

        for sock in self.sockets:
            sock.close()

    def dispatch_test_stop(self):
        loop = self.runner.get_loop()
        loop.call_soon_threadsafe(self.event.set)
