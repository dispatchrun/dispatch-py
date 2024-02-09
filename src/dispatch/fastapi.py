"""Integration of Dispatch programmable endpoints for FastAPI.

Example:

    import fastapi
    from dispatch.fastapi import Dispatch

    app = fastapi.FastAPI()
    dispatch = Dispatch(app, api_key="test-key")

    @dispatch.function()
    def my_function():
        return "Hello World!"

    @app.get("/")
    def read_root():
        dispatch.call(my_function)
    """

import base64
import logging
import os
from datetime import timedelta

import fastapi
import fastapi.responses
from http_message_signatures import InvalidSignature
from httpx import _urlparse

from dispatch.client import DEFAULT_API_URL, Client
from dispatch.function import Registry
from dispatch.proto import Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    public_key_from_bytes,
    public_key_from_pem,
    verify_request,
)
from dispatch.status import Status

logger = logging.getLogger(__name__)


class Dispatch(Registry):
    """A Dispatch programmable endpoint, powered by FastAPI."""

    def __init__(
        self,
        app: fastapi.FastAPI,
        endpoint: str | None = None,
        verification_key: Ed25519PublicKey | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
    ):
        """Initialize a Dispatch endpoint, and integrate it into a FastAPI app.

        It mounts a sub-app that implements the Dispatch gRPC interface.

        Args:
            app: The FastAPI app to configure.

            endpoint: Full URL of the application the Dispatch programmable
              endpoint will be running on. Uses the value of the
              DISPATCH_ENDPOINT_URL environment variable by default.

            verification_key: Key to use when verifying signed requests. Uses
              the value of the DISPATCH_VERIFICATION_KEY environment variable
              by default. The environment variable is expected to carry an
              Ed25519 public key in base64 or PEM format.

            api_key: Dispatch API key to use for authentication. Uses the value of
              the DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use. Uses the value of the
              DISPATCH_API_URL environment variable if set, otherwise
              defaults to the public Dispatch API (DEFAULT_DISPATCH_API_URL).

        Raises:
            ValueError: If any of the required arguments are missing.
        """
        if not app:
            raise ValueError("app is required")

        if not endpoint:
            endpoint = os.getenv("DISPATCH_ENDPOINT_URL")
        if not endpoint:
            raise ValueError("endpoint is required")

        if not verification_key:
            try:
                verification_key_raw = os.environ["DISPATCH_VERIFICATION_KEY"]
            except KeyError:
                pass
            else:
                # Be forgiving when accepting keys in PEM format.
                verification_key_raw = verification_key_raw.replace("\\n", "\n")
                try:
                    verification_key = public_key_from_pem(verification_key_raw)
                except ValueError:
                    verification_key = public_key_from_bytes(
                        base64.b64decode(verification_key_raw)
                    )

        logger.info("configuring Dispatch endpoint %s", endpoint)

        parsed_url = _urlparse.urlparse(endpoint)
        if not parsed_url.netloc or not parsed_url.scheme:
            raise ValueError("endpoint must be a full URL with protocol and domain")

        if verification_key:
            base64_key = base64.b64encode(verification_key.public_bytes_raw()).decode()
            logger.info("verifying request signatures using key %s", base64_key)
        else:
            logger.warning("request verification is disabled")

        if not api_key:
            api_key = os.environ.get("DISPATCH_API_KEY")
        if not api_url:
            api_url = os.environ.get("DISPATCH_API_URL", DEFAULT_API_URL)

        client = (
            Client(api_key=api_key, api_url=api_url) if api_key and api_url else None
        )

        super().__init__(endpoint, client)

        function_service = _new_app(self, verification_key)

        app.mount("/dispatch.sdk.v1.FunctionService", function_service)


class _GRPCResponse(fastapi.Response):
    media_type = "application/grpc+proto"


def _new_app(function_registry: Dispatch, verification_key: Ed25519PublicKey | None):
    app = fastapi.FastAPI()

    @app.post(
        # The endpoint for execution is hardcoded at the moment. If the service
        # gains more endpoints, this should be turned into a dynamic dispatch
        # like the official gRPC server does.
        "/Run",
        response_class=_GRPCResponse,
    )
    async def execute(request: fastapi.Request):
        # Raw request body bytes are only available through the underlying
        # starlette Request object's body method, which returns an awaitable,
        # forcing execute() to be async.
        data: bytes = await request.body()

        logger.debug("handling run request with %d byte body", len(data))

        if verification_key is not None:
            signed_request = Request(
                method=request.method,
                url=str(request.url),
                headers=CaseInsensitiveDict(request.headers),
                body=data,
            )
            max_age = timedelta(minutes=5)
            try:
                verify_request(signed_request, verification_key, max_age)
            except (InvalidSignature, ValueError):
                logger.error("failed to verify request signature", exc_info=True)
                raise fastapi.HTTPException(
                    status_code=403, detail="request signature is invalid"
                )
        else:
            logger.debug("skipping request signature verification")

        req = function_pb.RunRequest.FromString(data)

        if not req.function:
            raise fastapi.HTTPException(status_code=400, detail="function is required")

        try:
            func = function_registry._functions[req.function]
        except KeyError:
            logger.debug("function '%s' not found", req.function)
            raise fastapi.HTTPException(
                status_code=404, detail=f"Function '{req.function}' does not exist"
            )

        input = Input(req)

        logger.info("running function '%s'", req.function)
        try:
            output = func(input)
        except Exception:
            # This indicates that an exception was raised in a primitive
            # function. Primitive functions must catch exceptions, categorize
            # them in order to derive a Status, and then return a RunResponse
            # that carries the Status and the error details. A failure to do
            # so indicates a problem, and we return a 500 rather than attempt
            # to catch and categorize the error here.
            logger.error("function '%s' fatal error", req.function, exc_info=True)
            raise fastapi.HTTPException(
                status_code=500, detail=f"function '{req.function}' fatal error"
            )
        else:
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

        return fastapi.Response(content=response.SerializeToString())

    return app
