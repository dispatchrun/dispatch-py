from wsgiref.simple_server import make_server

from flask import Flask

import dispatch
import dispatch.test
from dispatch.flask import Dispatch
from dispatch.function import Registry


class TestFlask(dispatch.test.TestCase):

    def dispatch_test_init(self, reg: Registry) -> str:
        host = "127.0.0.1"
        port = 56789

        app = Flask("test")
        dispatch = Dispatch(app, registry=reg)

        self.wsgi = make_server(host, port, app)
        return f"http://{host}:{port}"

    def dispatch_test_run(self):
        self.wsgi.serve_forever(poll_interval=0.05)

    def dispatch_test_stop(self):
        self.wsgi.shutdown()
        self.wsgi.server_close()
