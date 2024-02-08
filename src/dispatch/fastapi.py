"""Integration of Dispatch programmable endpoints for FastAPI.

Example:

    import fastapi
    import dispatch.fastapi

    app = fastapi.FastAPI()
    dispatch.fastapi.configure(app, api_key="test-key")

    @app.dispatch_function()
    def my_function():
        return "Hello World!"

    @app.get("/")
    def read_root():
        my_function.call()
"""

import base64
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Dict

import fastapi
import fastapi.responses
from http_message_signatures import InvalidSignature
from httpx import _urlparse

import dispatch.function
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    verify_request,
)

logger = logging.getLogger(__name__)


def configure(
    app: fastapi.FastAPI,
    public_url: str,
    verification_key: Ed25519PublicKey | None = None,
):
    """Configure the FastAPI app to use Dispatch programmable endpoints.

    It mounts a sub-app that implements the Dispatch gRPC interface. It also
    adds a a decorator named @app.dispatch_function() to register functions.

    Args:
        app: The FastAPI app to configure.
        public_url: Full URL of the application the dispatch programmable
          endpoint will be running on.
        verification_key: Key to use when verifying signed requests.

    Raises:
        ValueError: If any of the required arguments are missing.
    """
    if not app:
        raise ValueError("app is required")
    if not public_url:
        raise ValueError("public_url is required")

    logger.info("configuring function service with public URL %s", public_url)

    parsed_url = _urlparse.urlparse(public_url)
    if not parsed_url.netloc or not parsed_url.scheme:
        raise ValueError("public_url must be a full URL with protocol and domain")

    if verification_key:
        base64_key = base64.b64encode(verification_key.public_bytes_raw()).decode()
        logger.info("verifying requests using key %s", base64_key)
    else:
        logger.warning("request verification is disabled")

    dispatch_app = _new_app(public_url, verification_key)

    app.__setattr__("dispatch_function", dispatch_app.dispatch_function)
    app.mount("/dispatch.sdk.v1.FunctionService", dispatch_app)


class _DispatchAPI(fastapi.FastAPI):
    def __init__(self, endpoint: str):
        super().__init__()
        self._functions: Dict[str, dispatch.function.Function] = {}
        self._endpoint = endpoint

    def dispatch_function(self):
        """Register a function with the Dispatch programmable endpoints.

        Args:
            app: The FastAPI app to register the function with.
            function: The function to register.

        Raises:
            ValueError: If the function is already registered.
        """

        def wrap(func: Callable[[dispatch.function.Input], dispatch.function.Output]):
            name = func.__qualname__
            logger.info("registering function '%s'", name)
            wrapped_func = dispatch.function.Function(self._endpoint, name, func)
            if name in self._functions:
                raise ValueError(f"Function {name} already registered")
            self._functions[name] = wrapped_func
            return wrapped_func

        return wrap


class _GRPCResponse(fastapi.Response):
    media_type = "application/grpc+proto"


def _new_app(endpoint: str, verification_key: Ed25519PublicKey | None):
    app = _DispatchAPI(endpoint)

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
            func = app._functions[req.function]
        except KeyError:
            logger.error("function '%s' not found", req.function)
            raise fastapi.HTTPException(
                status_code=404, detail=f"Function '{req.function}' does not exist"
            )

        input = dispatch.function.Input(req)

        logger.info("running function '%s'", req.function)
        try:
            output = func(input)
        except Exception as ex:
            logger.error(
                "function '%s' failed with an error", req.function, exc_info=True
            )
            # TODO: distinguish uncaught exceptions from exceptions returned by
            # coroutine?
            err = dispatch.function.Error.from_exception(ex)
            output = dispatch.function.Output.error(err)
        else:
            logger.debug("function '%s' ran successfully", req.function)

        resp = output._message
        logger.debug(
            "finished handling run request with status %s",
            dispatch.function.Status(resp.status).name,
        )

        return fastapi.Response(content=resp.SerializeToString())

    return app
