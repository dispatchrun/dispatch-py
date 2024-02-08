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
import os
from collections.abc import Callable
from datetime import timedelta
from types import FunctionType
from typing import Any, Dict

import fastapi
import fastapi.responses
from http_message_signatures import InvalidSignature
from httpx import _urlparse

import dispatch.function
from dispatch import DEFAULT_DISPATCH_API_URL, Client, DispatchID
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    public_key_from_bytes,
    public_key_from_pem,
    verify_request,
)

logger = logging.getLogger(__name__)


def configure(
    app: fastapi.FastAPI,
    endpoint: str | None = None,
    verification_key: Ed25519PublicKey | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
):
    """Configure the FastAPI app to use Dispatch programmable endpoints.

    It mounts a sub-app that implements the Dispatch gRPC interface. It also
    adds a decorator named @app.dispatch_function() to register functions.

    The app can optionally be configured to dispatch function calls that
    have been registered locally. If an api_key is provided,
    app.dispatch(fn, input) can be used to dispatch a call a local function
    via the Dispatch API.

    Args:
        app: The FastAPI app to configure.

        endpoint: Full URL of the application the Dispatch programmable
          endpoint will be running on. Uses the value of the DISPATCH_ENDPOINT
          environment variable by default.

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
        endpoint = os.getenv("DISPATCH_ENDPOINT")
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

    logger.info("configuring function service with endpoint %s", endpoint)

    parsed_url = _urlparse.urlparse(endpoint)
    if not parsed_url.netloc or not parsed_url.scheme:
        raise ValueError("endpoint must be a full URL with protocol and domain")

    if verification_key:
        base64_key = base64.b64encode(verification_key.public_bytes_raw()).decode()
        logger.info("verifying requests using key %s", base64_key)
    else:
        logger.warning("request verification is disabled")

    if not api_key:
        api_key = os.environ.get("DISPATCH_API_KEY")
    if not api_url:
        api_url = os.environ.get("DISPATCH_API_URL", DEFAULT_DISPATCH_API_URL)

    client = Client(api_key=api_key, api_url=api_url) if api_key and api_url else None

    dispatch_app = _new_app(endpoint, verification_key, client)

    app.__setattr__("dispatch_function", dispatch_app.dispatch_function)
    app.__setattr__("dispatch", dispatch_app.dispatch)
    app.mount("/dispatch.sdk.v1.FunctionService", dispatch_app)


class _DispatchAPI(fastapi.FastAPI):
    def __init__(self, endpoint: str, client: Client | None):
        super().__init__()
        self._dispatch_functions: Dict[str, dispatch.function.Function] = {}
        self._dispatch_endpoint = endpoint
        self._dispatch_client = client

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
            wrapped_func = dispatch.function.Function(
                self._dispatch_endpoint, name, func
            )
            if name in self._dispatch_functions:
                raise ValueError(f"Function {name} already registered")
            self._dispatch_functions[name] = wrapped_func
            return wrapped_func

        return wrap

    def dispatch(
        self, fn: FunctionType | dispatch.function.Function | str, input: Any = None
    ) -> DispatchID:
        """Dispatch a call to a local function.

        Args:
            fn: The function to dispatch a call to.
            input: Input to the function.

        Returns:
            DispatchID: ID of the dispatched call.

        Raises:
            RuntimeError: if a Dispatch client has not been configured.
            ValueError: if the function has not been registered.
        """
        if self._dispatch_client is None:
            raise RuntimeError(
                "Dispatch client has not been configured (api_key not provided when configuring FastAPI app)"
            )

        if isinstance(fn, FunctionType):
            fn = fn.__name__
        elif isinstance(fn, dispatch.function.Function):
            fn = fn.name

        try:
            wrapped_func = self._dispatch_functions[fn]
        except KeyError:
            raise ValueError(
                f"function {fn} has not been registered (via app.dispatch_function)"
            )

        [dispatch_id] = self._dispatch_client.dispatch([wrapped_func.call_with(input)])
        return dispatch_id


class _GRPCResponse(fastapi.Response):
    media_type = "application/grpc+proto"


def _new_app(
    endpoint: str, verification_key: Ed25519PublicKey | None, client: Client | None
):
    app = _DispatchAPI(endpoint, client)

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
            func = app._dispatch_functions[req.function]
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
