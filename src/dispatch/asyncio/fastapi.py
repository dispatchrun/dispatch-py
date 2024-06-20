"""Integration of Dispatch functions with FastAPI for handlers using asyncio.

Example:

    import fastapi
    from dispatch.asyncio.fastapi import Dispatch

    app = fastapi.FastAPI()
    dispatch = Dispatch(app)

    @dispatch.function
    def my_function():
        return "Hello World!"

    @app.get("/")
    async def read_root():
        await my_function.dispatch()
"""

import logging
from typing import Optional, Union

import fastapi
import fastapi.responses

from dispatch.function import Registry
from dispatch.http import (
    AsyncFunctionService,
    FunctionServiceError,
    validate_content_length,
)
from dispatch.signature import Ed25519PublicKey, parse_verification_key

logger = logging.getLogger(__name__)


class Dispatch(AsyncFunctionService):
    """A Dispatch instance, powered by FastAPI."""

    def __init__(
        self,
        app: fastapi.FastAPI,
        registry: Optional[Registry] = None,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
    ):
        """Initialize a Dispatch endpoint, and integrate it into a FastAPI app.

        It mounts a sub-app that implements the Dispatch gRPC interface.

        Args:
            app: The FastAPI app to configure.

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
                "missing FastAPI app as first argument of the Dispatch constructor"
            )
        super().__init__(registry, verification_key)
        function_service = fastapi.FastAPI()

        @function_service.exception_handler(FunctionServiceError)
        async def on_error(request: fastapi.Request, exc: FunctionServiceError):
            # https://connectrpc.com/docs/protocol/#error-end-stream
            return fastapi.responses.JSONResponse(
                status_code=exc.status,
                content={"code": exc.code, "message": exc.message},
            )

        @function_service.post(
            # The endpoint for execution is hardcoded at the moment. If the service
            # gains more endpoints, this should be turned into a dynamic dispatch
            # like the official gRPC server does.
            "/Run",
        )
        async def run(request: fastapi.Request):
            valid, reason = validate_content_length(
                int(request.headers.get("content-length", 0))
            )
            if not valid:
                raise FunctionServiceError(400, "invalid_argument", reason)

            # Raw request body bytes are only available through the underlying
            # starlette Request object's body method, which returns an awaitable,
            # forcing execute() to be async.
            data: bytes = await request.body()

            content = await self.run(
                str(request.url),
                request.method,
                request.headers,
                await request.body(),
            )

            return fastapi.Response(content=content, media_type="application/proto")

        app.mount("/dispatch.sdk.v1.FunctionService", function_service)
