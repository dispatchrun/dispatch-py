"""Integration of Dispatch functions with FastAPI.

Example:

    import fastapi
    from dispatch.fastapi import Dispatch

    app = fastapi.FastAPI()
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
from typing import Optional, Union

import fastapi
import fastapi.responses

from dispatch.function import Registry
from dispatch.http import FunctionServiceError, function_service_run
from dispatch.signature import Ed25519PublicKey, parse_verification_key

logger = logging.getLogger(__name__)


class Dispatch(Registry):
    """A Dispatch instance, powered by FastAPI."""

    def __init__(
        self,
        app: fastapi.FastAPI,
        endpoint: Optional[str] = None,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """Initialize a Dispatch endpoint, and integrate it into a FastAPI app.

        It mounts a sub-app that implements the Dispatch gRPC interface.

        Args:
            app: The FastAPI app to configure.

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
                "missing FastAPI app as first argument of the Dispatch constructor"
            )
        super().__init__(endpoint, api_key=api_key, api_url=api_url)
        verification_key = parse_verification_key(verification_key, endpoint=endpoint)
        function_service = _new_app(self, verification_key)
        app.mount("/dispatch.sdk.v1.FunctionService", function_service)


def _new_app(function_registry: Registry, verification_key: Optional[Ed25519PublicKey]):
    app = fastapi.FastAPI()

    @app.exception_handler(FunctionServiceError)
    async def on_error(request: fastapi.Request, exc: FunctionServiceError):
        # https://connectrpc.com/docs/protocol/#error-end-stream
        return fastapi.responses.JSONResponse(
            status_code=exc.status, content={"code": exc.code, "message": exc.message}
        )

    @app.post(
        # The endpoint for execution is hardcoded at the moment. If the service
        # gains more endpoints, this should be turned into a dynamic dispatch
        # like the official gRPC server does.
        "/Run",
    )
    async def execute(request: fastapi.Request):
        # Raw request body bytes are only available through the underlying
        # starlette Request object's body method, which returns an awaitable,
        # forcing execute() to be async.
        data: bytes = await request.body()

        content = await function_service_run(
            str(request.url),
            request.method,
            request.headers,
            data,
            function_registry,
            verification_key,
        )

        return fastapi.Response(content=content, media_type="application/proto")

    return app
