import asyncio
import socket
<<<<<<< HEAD
from http.server import HTTPServer

import dispatch.test
from dispatch.asyncio import Runner
from dispatch.function import Registry
from dispatch.http import Dispatch, FunctionService, Server


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

        self.aiowait = asyncio.Event()
        self.aioloop = Runner()
        self.aiohttp = Server(host, port, Dispatch(reg))
        self.aioloop.run(self.aiohttp.start())

        return f"http://{self.aiohttp.host}:{self.aiohttp.port}"

    def dispatch_test_run(self):
        self.aioloop.run(self.aiowait.wait())
        self.aioloop.run(self.aiohttp.stop())
        self.aioloop.close()

    def dispatch_test_stop(self):
        self.aioloop.get_loop().call_soon_threadsafe(self.aiowait.set)
=======
from datetime import datetime
from http.server import HTTPServer

import dispatch.test
from dispatch.function import Registry
from dispatch.http import Dispatch, Server


class TestHTTP(dispatch.test.TestCase):

    def dispatch_test_init(self, api_key: str, api_url: str) -> Registry:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("localhost", 0))
        sock.listen(128)

        (host, port) = sock.getsockname()

        reg = Registry(
            endpoint=f"http://{host}:{port}",
            api_key=api_key,
            api_url=api_url,
        )

        self.httpserver = HTTPServer(
            server_address=(host, port),
            RequestHandlerClass=Dispatch(reg),
            bind_and_activate=False,
        )
        self.httpserver.socket = sock
        return reg

    def dispatch_test_run(self):
        self.httpserver.serve_forever(poll_interval=0.05)

    def dispatch_test_stop(self):
        self.httpserver.shutdown()
        self.httpserver.server_close()


class TestAIOHTTP(dispatch.test.TestCase):

    def dispatch_test_init(self, api_key: str, api_url: str) -> Registry:
        host = "localhost"
        port = 0

        reg = Registry(
            endpoint=f"http://{host}:{port}",
            api_key=api_key,
            api_url=api_url,
        )

        self.aioloop = asyncio.new_event_loop()
        self.aiohttp = Server(host, port, Dispatch(reg))
        self.aioloop.run_until_complete(self.aiohttp.start())

        reg.endpoint = f"http://{self.aiohttp.host}:{self.aiohttp.port}"
        return reg

    def dispatch_test_run(self):
        self.aioloop.run_forever()

    def dispatch_test_stop(self):
        def stop():
            self.aiohttp.stop()
            self.aioloop.stop()

        self.aioloop.call_soon_threadsafe(stop)
>>>>>>> ed50efc (port http tests to generic dispatch test suite)
