"""Integration of Dispatch programmable endpoints for FastAPI.

Example:

    import fastapi
    import dispatch.fastapi

    app = fastapi.FastAPI()
    dispatch.fastapi.configure(app, api_key="test-key")

    @app.dispatch_coroutine()
    def my_cool_coroutine():
        return "Hello World!"

    @app.get("/")
    def read_root():
        my_cool_coroutine.call()
"""

import os
from collections.abc import Callable
from typing import Any, Dict

import fastapi
import fastapi.responses
from httpx import _urlparse

import dispatch.coroutine
from dispatch.sdk.v1 import executor_pb2 as executor_pb


def configure(
    app: fastapi.FastAPI,
    public_url: str,
    api_key: None | str = None,
):
    """Configure the FastAPI app to use Dispatch programmable endpoints.

    It mounts a sub-app that implements the Dispatch gRPC interface. It also
    adds a a decorator named @app.dispatch_coroutine() to register coroutines.

    Args:
        app: The FastAPI app to configure.
        api_key: Dispatch API key to use for authentication. Uses the value of
          the DISPATCH_API_KEY environment variable by default.
        public_url: Full URL of the application the dispatch programmable
          endpoint will be running on.

    Raises:
        ValueError: If any of the required arguments are missing.
    """
    api_key = api_key or os.environ.get("DISPATCH_API_KEY")

    if not app:
        raise ValueError("app is required")
    if not public_url:
        raise ValueError("public_url is required")
    if not api_key:
        raise ValueError("api_key is required")

    parsed_url = _urlparse.urlparse(public_url)
    if not parsed_url.netloc or not parsed_url.scheme:
        raise ValueError("public_url must be a full URL with protocol and domain")

    dispatch_app = _new_app(public_url)

    app.__setattr__("dispatch_coroutine", dispatch_app.dispatch_coroutine)
    app.mount("/dispatch.sdk.v1.ExecutorService", dispatch_app)


class _DispatchAPI(fastapi.FastAPI):
    def __init__(self, public_url: str):
        super().__init__()
        self._coroutines: Dict[str, dispatch.coroutine.Coroutine] = {}
        self._public_url = _urlparse.urlparse(public_url)

    def dispatch_coroutine(self):
        """Register a coroutine with the Dispatch programmable endpoints.

        Args:
            app: The FastAPI app to register the coroutine with.
            coroutine: The coroutine to register.

        Raises:
            ValueError: If the coroutine is already registered.
        """

        def wrap(func: Callable[[dispatch.coroutine.Input], dispatch.coroutine.Output]):
            name = func.__qualname__
            uri = str(self._public_url.copy_with(fragment="function=" + name))
            coro = dispatch.coroutine.Coroutine(uri, func)
            if coro.uri in self._coroutines:
                raise ValueError(f"Coroutine {coro.uri} already registered")
            self._coroutines[coro.uri] = coro
            return coro

        return wrap


class _GRPCResponse(fastapi.Response):
    media_type = "application/grpc+proto"


def _new_app(public_url: str):
    app = _DispatchAPI(public_url)

    @app.post(
        # The endpoint for execution is hardcoded at the moment. If the service
        # gains more endpoints, this should be turned into a dynamic dispatch
        # like the official gRPC server does.
        "/Execute",
        response_class=_GRPCResponse,
    )
    async def execute(request: fastapi.Request):
        # Raw request body bytes are only available through the underlying
        # starlette Request object's body method, which returns an awaitable,
        # forcing execute() to be async.
        data: bytes = await request.body()

        req = executor_pb.ExecuteRequest.FromString(data)

        if not req.coroutine_uri:
            raise fastapi.HTTPException(
                status_code=400, detail="coroutine_uri is required"
            )

        # TODO: be more graceful. This will crash if the coroutine is not found,
        # and the coroutine version is not taken into account.

        uri = req.coroutine_uri

        coroutine = app._coroutines.get(uri, None)
        if coroutine is None:
            # TODO: integrate with logging
            raise fastapi.HTTPException(
                status_code=404, detail=f"Coroutine URI '{uri}' does not exist"
            )

        coro_input = dispatch.coroutine.Input(req)

        try:
            output = coroutine(coro_input)
        except Exception as ex:
            # TODO: distinguish uncaught exceptions from exceptions returned by
            # coroutine?
            err = dispatch.coroutine.Error.from_exception(ex)
            output = dispatch.coroutine.Output.error(err)

        resp = output._message
        resp.coroutine_uri = req.coroutine_uri
        resp.coroutine_version = req.coroutine_version

        return fastapi.Response(content=resp.SerializeToString())

    return app
