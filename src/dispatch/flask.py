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

import logging
from typing import Optional, Union

from flask import Flask, make_response, request

from dispatch.asyncio import Runner
from dispatch.function import Registry
from dispatch.http import FunctionServiceError, function_service_run
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

    def _handle_error(self, exc: FunctionServiceError):
        return {"code": exc.code, "message": exc.message}, exc.status

    def _execute(self):
        data: bytes = request.get_data(cache=False)

        with Runner() as runner:
            content = runner.run(
                function_service_run(
                    request.url,
                    request.method,
                    dict(request.headers),
                    data,
                    self,
                    self._verification_key,
                ),
            )

        res = make_response(content)
        res.content_type = "application/proto"
        return res
