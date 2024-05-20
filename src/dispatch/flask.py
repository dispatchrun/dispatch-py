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

from dispatch.function import Registry
from dispatch.proto import Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    parse_verification_key,
    verify_request,
)
from dispatch.status import Status

logger = logging.getLogger(__name__)


class _ConnectError(Exception):
    __slots__ = ("status", "code", "message")

    def __init__(self, status, code, message):
        super().__init__(status)
        self.status = status
        self.code = code
        self.message = message


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

        app.errorhandler(_ConnectError)(self._handle_error)

        app.post("/dispatch.sdk.v1.FunctionService/Run")(self._execute)

    def _handle_error(self, exc: _ConnectError):
        return {"code": exc.code, "message": exc.message}, exc.status

    def _execute(self):
        data: bytes = request.get_data(cache=False)
        logger.debug("handling run request with %d byte body", len(data))

        # TODO: verification key

        req = function_pb.RunRequest.FromString(data)
        if not req.function:
            raise _ConnectError(400, "invalid_argument", "function is required")

        try:
            func = self.functions[req.function]
        except KeyError:
            logger.debug("function '%s' not found", req.function)
            raise _ConnectError(
                404, "not_found", f"function '{req.function}' does not exist"
            )

        input = Input(req)
        logger.info("running function '%s'", req.function)

        try:
            output = func._primitive_call(input)
        except Exception:
            # This indicates that an exception was raised in a primitive
            # function. Primitive functions must catch exceptions, categorize
            # them in order to derive a Status, and then return a RunResponse
            # that carries the Status and the error details. A failure to do
            # so indicates a problem, and we return a 500 rather than attempt
            # to catch and categorize the error here.
            logger.error("function '%s' fatal error", req.function, exc_info=True)
            raise _ConnectError(
                500, "internal", f"function '{req.function}' fatal error"
            )

        response = output._message
        status = Status(response.status)

        if response.HasField("poll"):
            logger.debug(
                "function '%s' polling with %d call(s)",
                req.function,
                len(response.poll.calls),
            )
        elif response.HasField("exit"):
            exit = response.exit
            if not exit.HasField("result"):
                logger.debug("function '%s' exiting with no result", req.function)
            else:
                result = exit.result
                if result.HasField("output"):
                    logger.debug(
                        "function '%s' exiting with output value", req.function
                    )
                elif result.HasField("error"):
                    err = result.error
                    logger.debug(
                        "function '%s' exiting with error: %s (%s)",
                        req.function,
                        err.message,
                        err.type,
                    )
            if exit.HasField("tail_call"):
                logger.debug(
                    "function '%s' tail calling function '%s'",
                    exit.tail_call.function,
                )

        logger.debug("finished handling run request with status %s", status.name)
        res = make_response(response.SerializeToString())
        res.content_type = "application/proto"
        return res
