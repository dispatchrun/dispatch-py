"""Integration of Dispatch functions with Flask.

Example:

    from flask import Flask
    from dispatch.flask import Dispatch

    app = Flask(__name__)
    dispatch = Dispatch(app)

    @dispatch.function
    def my_function():
        return "Hello World!"

    @app.get("/")
    def read_root():
        my_function.dispatch()
    """

import asyncio
import logging
from typing import Optional, Union

from flask import Flask, make_response, request

from dispatch.function import Registry
from dispatch.http import (
    BlockingFunctionService,
    FunctionServiceError,
    validate_content_length,
)
from dispatch.signature import Ed25519PublicKey, parse_verification_key

logger = logging.getLogger(__name__)


class Dispatch(BlockingFunctionService):
    """A Dispatch instance, powered by Flask."""

    def __init__(
        self,
        app: Flask,
        registry: Optional[Registry] = None,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
    ):
        """Initialize a Dispatch endpoint, and integrate it into a Flask app.

        It mounts a sub-app that implements the Dispatch gRPC interface.

        Args:
            app: The Flask app to configure.

            registry: A registry of functions to expose. If omitted, the default
                registry is used.

            verification_key: Key to use when verifying signed requests. Uses
                the value of the DISPATCH_VERIFICATION_KEY environment variable
                if omitted. The environment variable is expected to carry an
                Ed25519 public key in base64 or PEM format.
                If not set, request signature verification is disabled (a warning
                will be logged by the constructor).

        Raises:
            ValueError: If any of the required arguments are missing.
        """
        if not app:
            raise ValueError(
                "missing Flask app as first argument of the Dispatch constructor"
            )
        super().__init__(registry, verification_key)
        app.errorhandler(FunctionServiceError)(self._on_error)
        app.post("/dispatch.sdk.v1.FunctionService/Run")(self._run)

    def _on_error(self, exc: FunctionServiceError):
        return {"code": exc.code, "message": exc.message}, exc.status

    def _run(self):
        valid, reason = validate_content_length(request.content_length or 0)
        if not valid:
            return {"code": "invalid_argument", "message": reason}, 400

        content = asyncio.run(
            self.run(
                request.url,
                request.method,
                dict(request.headers),
                request.get_data(cache=False),
            )
        )

        res = make_response(content)
        res.content_type = "application/proto"
        return res
