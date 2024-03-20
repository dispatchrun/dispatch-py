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
        my_function.dispatch()
    """

import base64
import logging
import os
import sys
import threading
import time
from typing import Any
from datetime import timedelta
from urllib.parse import urlparse

import fastapi
import fastapi.responses
from http_message_signatures import InvalidSignature

from dispatch.function import Batch, Client, Registry
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

    __slots__ = ("client", "_api_key_provided", "_app")

    def __init__(
        self,
        app: fastapi.FastAPI,
        endpoint: str | None = None,
        verification_key: Ed25519PublicKey | str | bytes | None = None,
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

        self._app = app
        self._api_key_provided = api_key is not None

        endpoint_from = "endpoint argument"
        if not endpoint:
            endpoint = os.getenv("DISPATCH_ENDPOINT_URL")
            endpoint_from = "DISPATCH_ENDPOINT_URL"
        if not endpoint:
            if not api_key:
                logger.warning("Application endpoint not provided. Running in local development mode. Set DISPATCH_ENDPOINT_URL and DISPATCH_API_KEY in production.")
                endpoint = "http://localhost:0"
                endpoint_from = "local fallback endpoint"
                api_key = "invalid_key"
            else:
                raise ValueError(
                    "missing application endpoint: set it with the DISPATCH_ENDPOINT_URL environment variable"
                )

        logger.info("configuring Dispatch endpoint %s", endpoint)

        parsed_url = urlparse(endpoint)
        if not parsed_url.netloc or not parsed_url.scheme:
            raise ValueError(
                f"{endpoint_from} must be a full URL with protocol and domain (e.g., https://example.com)"
            )

        verification_key = parse_verification_key(verification_key)
        if verification_key:
            base64_key = base64.b64encode(verification_key.public_bytes_raw()).decode()
            logger.info("verifying request signatures using key %s", base64_key)
        else:
            logger.warning(
                "request verification is disabled because DISPATCH_VERIFICATION_KEY is not set"
            )

        self.client = Client(api_key=api_key, api_url=api_url)
        super().__init__(endpoint, self.client)

        function_service = _new_app(self, verification_key)
        app.mount("/dispatch.sdk.v1.FunctionService", function_service)

    def batch(self) -> Batch:
        """Returns a Batch instance that can be used to build
        a set of calls to dispatch."""
        return self.client.batch()

    def run(self, uvicorn_args:dict[str, Any]|None=None):
        """Run the FastAPI application that uses this Dispatch instance.

        It is equivalent to uvicorn.run(app). If the Dispatch API key is not
        provided, a local development server is automatically spun up.

        """
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())

        # Import here because user may not be using run() and may be using a
        # different server than uvicorn.
        import uvicorn

        if uvicorn_args is None:
            uvicorn_args = {}

        if self._api_key_provided:
            uvicorn.run(self._app, **uvicorn_args)
            return

        # If the Dispatch API key was not provided to this object, start a local
        # instance of the mock Dispatch API server.
        #
        # By default, bind the uvicorn server to port 0 to not force the user to
        # make a choice. This is useful for local development. As a result, the
        # uvicorn server needs to be started first to know the port that ends up
        # being bound to figure out the endpoint URL. However, since all
        # dispatch functions use the endpoint URL as part of their name, and
        # their name is calculated at the time of definition, we need to remap
        # all the functions in this registry to update their endpoint.


        uvicorn_args["port"] = 0
        uv_config = uvicorn.Config(self._app, **uvicorn_args)
        uv_server = uvicorn.Server(uv_config)

        uv_thread = threading.Thread(target=uv_server.run, daemon=True)
        uv_thread.start()

        max_seconds = 5
        start = time.monotonic_ns()
        while True:
            now = time.monotonic_ns()
            if now - start >= 10e9 * max_seconds:
                raise RuntimeError(f"uvicorn server has not started in {max_seconds}s")
            if not uv_thread.is_alive():
                raise RuntimeError("uvicorn server crashed")
            if uv_server.started:
                break
            time.sleep(0.01)

        host, port = uv_server.servers[0].sockets[0].getsockname()
        endpoint = f"http://{host}:{port}"
        logger.info("Spawned uvicorn server at %s", endpoint)

        api_url = None
        cv = threading.Condition()

        api_key = "this_is_a_local_server_api_key"

        def start_test_server():
            from dispatch.test import DispatchServer, DispatchService, EndpointClient


            endpoint_client = EndpointClient.from_url(endpoint)

            logger.debug("Starting the dispatch service")
            with DispatchService(endpoint_client, api_key=api_key) as service:
                with DispatchServer(service) as server:
                    logger.debug("Dispatch server ready")
                    with cv:
                        nonlocal api_url
                        api_url = server.url
                        cv.notify_all()
                    server.wait()

        api_thread = threading.Thread(target=start_test_server, daemon=True)
        api_thread.start()

        timeout_s = 10.0
        with cv:
            if cv.wait_for(lambda: api_url is not None, timeout_s) is False:
                raise RuntimeError(f"Failed to start the test server in {timeout_s}s")
        logger.info("Spawned a mock Dispatch server at %s", api_url)

        # At this point, both the local Dispatch API server and the uvicorn
        # server are ready. Recreate the client and re-name all the known
        # functions.
        self.client = Client(api_key=api_key, api_url=api_url)
        self._client = self.client
        self._endpoint = endpoint

        for fn in self._functions.values():
            fn._client = self._client
            fn._endpoint = self._endpoint

        logger.info(f"""
🚀 Dispatch ready.

Example use:

    curl {endpoint}
""")


        try:
            while True:
                if not uv_thread.is_alive() or not api_thread.is_alive():
                    break
                time.sleep(0.01)
        except KeyboardInterrupt:
            sys.exit(0)


def parse_verification_key(
    verification_key: Ed25519PublicKey | str | bytes | None,
) -> Ed25519PublicKey | None:
    if isinstance(verification_key, Ed25519PublicKey):
        return verification_key

    from_env = False
    if not verification_key:
        try:
            verification_key = os.environ["DISPATCH_VERIFICATION_KEY"]
        except KeyError:
            return None
        from_env = True

    if isinstance(verification_key, bytes):
        verification_key = verification_key.decode()

    # Be forgiving when accepting keys in PEM format, which may span
    # multiple lines. Users attempting to pass a PEM key via an environment
    # variable may accidentally include literal "\n" bytes rather than a
    # newline char (0xA).
    try:
        return public_key_from_pem(verification_key.replace("\\n", "\n"))
    except ValueError:
        pass

    try:
        return public_key_from_bytes(base64.b64decode(verification_key.encode()))
    except ValueError:
        if from_env:
            raise ValueError(f"invalid DISPATCH_VERIFICATION_KEY '{verification_key}'")
        raise ValueError(f"invalid verification key '{verification_key}'")


class _ConnectResponse(fastapi.Response):
    media_type = "application/grpc+proto"


class _ConnectError(fastapi.HTTPException):
    __slots__ = ("status", "code", "message")

    def __init__(self, status, code, message):
        super().__init__(status)
        self.status = status
        self.code = code
        self.message = message


def _new_app(function_registry: Dispatch, verification_key: Ed25519PublicKey | None):
    app = fastapi.FastAPI()

    @app.exception_handler(_ConnectError)
    async def on_error(request: fastapi.Request, exc: _ConnectError):
        # https://connectrpc.com/docs/protocol/#error-end-stream
        return fastapi.responses.JSONResponse(
            status_code=exc.status, content={"code": exc.code, "message": exc.message}
        )

    @app.post(
        # The endpoint for execution is hardcoded at the moment. If the service
        # gains more endpoints, this should be turned into a dynamic dispatch
        # like the official gRPC server does.
        "/Run",
        response_class=_ConnectResponse,
    )
    async def execute(request: fastapi.Request):
        # Raw request body bytes are only available through the underlying
        # starlette Request object's body method, which returns an awaitable,
        # forcing execute() to be async.
        data: bytes = await request.body()
        logger.debug("handling run request with %d byte body", len(data))

        if verification_key is None:
            logger.debug("skipping request signature verification")
        else:
            signed_request = Request(
                method=request.method,
                url=str(request.url),
                headers=CaseInsensitiveDict(request.headers),
                body=data,
            )
            max_age = timedelta(minutes=5)
            try:
                verify_request(signed_request, verification_key, max_age)
            except ValueError as e:
                raise _ConnectError(401, "unauthenticated", str(e))
            except InvalidSignature as e:
                # The http_message_signatures package sometimes wraps does not
                # attach a message to the exception, so we set a default to
                # have some context about the reason for the error.
                message = str(e) or "invalid signature"
                raise _ConnectError(403, "permission_denied", message)

        req = function_pb.RunRequest.FromString(data)
        if not req.function:
            raise _ConnectError(400, "invalid_argument", "function is required")

        try:
            func = function_registry._functions[req.function]
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
        return fastapi.Response(
            content=response.SerializeToString(), media_type="application/proto"
        )

    return app
