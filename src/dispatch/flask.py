"""Integration of Dispatch functions with Flask.

Example:

    from flask import Flask
    from dispatch.flask import Dispatch

    app = Flask(__name__)
    dispatch = Dispatch(app, api_key="test-key")

    @dispatch.function
    def my_function():
        return "Hello World!"

    @app.get("/")
    def read_root():
        my_function.dispatch()
    """

import asyncio
import logging
import threading
# from queue import Queue
from typing import Optional, Union

from flask import Flask, make_response, request

from dispatch.function import Registry
from dispatch.http import (
    FunctionServiceError,
    function_service_run,
    validate_content_length,
)
from dispatch.signature import Ed25519PublicKey, parse_verification_key

logger = logging.getLogger(__name__)


class Dispatch(Registry):
    """A Dispatch instance, powered by Flask."""

    def __init__(
        self,
        app: Flask,
        endpoint: Optional[str] = None,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """Initialize a Dispatch endpoint, and integrate it into a Flask app.

        It mounts a sub-app that implements the Dispatch gRPC interface.

        Args:
            app: The Flask app to configure.

            endpoint: Full URL of the application the Dispatch instance will
                be running on. Uses the value of the DISPATCH_ENDPOINT_URL
                environment variable by default.

            verification_key: Key to use when verifying signed requests. Uses
                the value of the DISPATCH_VERIFICATION_KEY environment variable
                if omitted. The environment variable is expected to carry an
                Ed25519 public key in base64 or PEM format.
                If not set, request signature verification is disabled (a warning
                will be logged by the constructor).

            api_key: Dispatch API key to use for authentication. Uses the value of
                the DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use. Uses the value of the
                DISPATCH_API_URL environment variable if set, otherwise
                defaults to the public Dispatch API (DEFAULT_API_URL).

        Raises:
            ValueError: If any of the required arguments are missing.
        """
        if not app:
            raise ValueError(
                "missing Flask app as first argument of the Dispatch constructor"
            )

        super().__init__(endpoint, api_key=api_key, api_url=api_url)

        self._verification_key = parse_verification_key(
            verification_key, endpoint=endpoint
        )

        app.errorhandler(FunctionServiceError)(self._handle_error)
        app.post("/dispatch.sdk.v1.FunctionService/Run")(self._execute)

        # TODO: earlier experiment I ran because it seemed like tasks created
        # by the /Dispatch endpoint were canceled when calls to /Wait were made.
        #
        # After further investigation, it might have been caused by a bug when
        # setting the thread local state indicating that we are being invoked
        # from a scheduler thread, which resulted in unnecessary dispatch calls.
        #
        # I'm keeping the code around for now in case it ends up being needed in
        # the short term. Feel free to remove if you run into this comment and
        # it's no longer relevant.
        # ---
        # Here we have to use one event loop for the whole application to allow
        # tasks spawned by request handlers to persist after the request is done.
        #
        # This is essential for tests to pass when using the /Dispatch and /Wait
        # endpoints to wait on function results.
        # self._loop = asyncio.new_event_loop()
        # self._thread = threading.Thread(target=self._run_event_loop)
        # self._thread.start()

    # def close(self):
    #     self._loop.call_soon_threadsafe(self._loop.stop)
    #     self._thread.join()

    # def __enter__(self):
    #     return self

    # def __exit__(self, exc_type, exc_value, traceback):
    #     self.close()

    # def _run_event_loop(self):
    #     asyncio.set_event_loop(self._loop)
    #     self._loop.run_forever()
    #     self._loop.run_until_complete(self._loop.shutdown_asyncgens())
    #     self._loop.close()

    def _handle_error(self, exc: FunctionServiceError):
        return {"code": exc.code, "message": exc.message}, exc.status

    def _execute(self):
        valid, reason = validate_content_length(request.content_length or 0)
        if not valid:
            return {"code": "invalid_argument", "message": reason}, 400

        data: bytes = request.get_data(cache=False)

        content = asyncio.run(
            function_service_run(
                request.url,
                request.method,
                dict(request.headers),
                data,
                self,
                self._verification_key,
            )
        )

        # queue = Queue[asyncio.Task](maxsize=1)
        #
        # url, method, headers = request.url, request.method, dict(request.headers)
        # def execute_task():
        #     task = self._loop.create_task(
        #         function_service_run(
        #             url,
        #             method,
        #             headers,
        #             data,
        #             self,
        #             self._verification_key,
        #         )
        #     )
        #     task.add_done_callback(queue.put)

        # self._loop.call_soon_threadsafe(execute_task)
        # task: asyncio.Task = queue.get()

        # exception = task.exception()
        # if exception is not None:
        #     raise exception

        # content: bytes = task.result()

        res = make_response(content)
        res.content_type = "application/proto"
        return res
