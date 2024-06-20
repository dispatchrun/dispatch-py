import asyncio
import socket
import sys
from http.server import HTTPServer

import dispatch.test
from dispatch.asyncio import Runner
from dispatch.function import Registry
from dispatch.http import Dispatch, Server


class TestHTTP(dispatch.test.TestCase):

    def dispatch_test_init(self, reg: Registry) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)

        (host, port) = sock.getsockname()

        self.httpserver = HTTPServer(
            server_address=(host, port),
            RequestHandlerClass=Dispatch(reg),
            bind_and_activate=False,
        )
        self.httpserver.socket = sock
        return f"http://{host}:{port}"

    def dispatch_test_run(self):
        self.httpserver.serve_forever(poll_interval=0.05)

    def dispatch_test_stop(self):
        self.httpserver.shutdown()
        self.httpserver.server_close()
        self.httpserver.socket.close()


class TestAIOHTTP(dispatch.test.TestCase):

    def dispatch_test_init(self, reg: Registry) -> str:
        host = "127.0.0.1"
        port = 0

        self.aioloop = Runner()
        self.aiohttp = Server(host, port, Dispatch(reg))
        self.aioloop.run(self.aiohttp.start())

        if sys.version_info >= (3, 10):
            self.aiowait = asyncio.Event()
        else:
            self.aiowait = asyncio.Event(loop=self.aioloop.get_loop())

        return f"http://{self.aiohttp.host}:{self.aiohttp.port}"

    def dispatch_test_run(self):
        self.aioloop.run(self.aiowait.wait())
        self.aioloop.run(self.aiohttp.stop())
        self.aioloop.close()

    def dispatch_test_stop(self):
        self.aioloop.get_loop().call_soon_threadsafe(self.aiowait.set)
