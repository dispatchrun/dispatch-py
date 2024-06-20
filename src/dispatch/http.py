"""Integration of Dispatch functions with http."""

import asyncio
import logging
from datetime import timedelta
from http.server import BaseHTTPRequestHandler
from typing import (
    Any,
    Callable,
    Coroutine,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from aiohttp import ClientConnectionError, web
from http_message_signatures import InvalidSignature
from typing_extensions import ParamSpec, TypeAlias

from dispatch.function import (
    AsyncFunction,
    Batch,
    BlockingFunction,
    Registry,
    _calls,
    default_registry,
)
from dispatch.proto import CallResult, Input
from dispatch.sdk.v1 import function_pb2 as function_pb
from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    Request,
    parse_verification_key,
    verify_request,
)
from dispatch.status import Status, register_error_type

# https://docs.aiohttp.org/en/stable/client_reference.html
register_error_type(ClientConnectionError, Status.TCP_ERROR)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class BaseFunctionService:
    """FunctionService is an abstract class intended to be inherited by objects
    that integrate dispatch with other server application frameworks.

    An application encapsulates a function Registry, and implements the API
    common to all dispatch integrations.
    """

    def __init__(
        self,
        registry: Optional[Registry] = None,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
    ):
        self._registry = registry
        self._verification_key = parse_verification_key(
            verification_key,
            endpoint=self.registry.endpoint,
        )

    @property
    def registry(self) -> Registry:
        return self._registry or default_registry()

    @property
    def verification_key(self) -> Optional[Ed25519PublicKey]:
        return self._verification_key

    def batch(self) -> Batch:
        """Create a new batch."""
        return self.registry.batch()

    async def run(
        self, url: str, method: str, headers: Mapping[str, str], data: bytes
    ) -> bytes:
        return await function_service_run(
            url,
            method,
            headers,
            data,
            self.registry,
            self.verification_key,
        )


class AsyncFunctionService(BaseFunctionService):
    @overload
    def function(
        self, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> AsyncFunction[P, T]: ...

    @overload
    def function(self, func: Callable[P, T]) -> AsyncFunction[P, T]: ...

    def function(self, func):
        return self.registry.function(func)


class BlockingFunctionService(BaseFunctionService):
    """BlockingFunctionService is a variant of FunctionService which decorates
    dispatch functions with a synchronous API instead of using asyncio.
    """

    @overload
    def function(self, func: Callable[P, T]) -> BlockingFunction[P, T]: ...

    @overload
    def function(
        self, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> BlockingFunction[P, T]: ...

    def function(self, func):
        return BlockingFunction(self.registry.function(func))


class FunctionServiceError(Exception):
    __slots__ = ("status", "code", "message")

    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message


def validate_content_length(content_length: int) -> Tuple[bool, str]:
    if content_length == 0:
        return False, "content length is required"
    if content_length < 0:
        return False, "content length is negative"
    if content_length > 16_000_000:
        return False, "content length is too large"
    return True, ""


class FunctionServiceHTTPRequestHandler(BaseHTTPRequestHandler):

    def __init__(
        self,
        request,
        client_address,
        server,
        registry: Registry,
        verification_key: Optional[Ed25519PublicKey] = None,
    ):
        self.registry = registry
        self.verification_key = verification_key
        self.error_content_type = "application/json"
        super().__init__(request, client_address, server)

    def send_error_response_invalid_argument(self, message: str):
        self.send_error_response(400, "invalid_argument", message)

    def send_error_response_not_found(self, message: str):
        self.send_error_response(404, "not_found", message)

    def send_error_response_unauthenticated(self, message: str):
        self.send_error_response(401, "unauthenticated", message)

    def send_error_response_permission_denied(self, message: str):
        self.send_error_response(403, "permission_denied", message)

    def send_error_response_internal(self, message: str):
        self.send_error_response(500, "internal", message)

    def send_error_response(self, status: int, code: str, message: str):
        body = make_error_response_body(code, message)
        self.send_response(status)
        self.send_header("Content-Type", self.error_content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/dispatch.sdk.v1.FunctionService/Run":
            self.send_error_response_not_found("path not found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        valid, reason = validate_content_length(content_length)
        if not valid:
            self.send_error_response_invalid_argument(reason)
            return

        data: bytes = self.rfile.read(content_length)

        method = "POST"
        url = self.requestline  # TODO: need full URL

        try:
            content = asyncio.run(
                function_service_run(
                    url,
                    method,
                    dict(self.headers),
                    data,
                    self.registry,
                    self.verification_key,
                )
            )
        except FunctionServiceError as e:
            return self.send_error_response(e.status, e.code, e.message)

        self.send_response(200)
        self.send_header("Content-Type", "application/proto")
        self.end_headers()
        self.wfile.write(content)


class Dispatch(web.Application):
    """A Dispatch instance servicing as a http server."""

    registry: Registry
    verification_key: Optional[Ed25519PublicKey]

    def __init__(
        self,
        registry: Registry,
        verification_key: Optional[Union[Ed25519PublicKey, str, bytes]] = None,
    ):
        """Initialize a Dispatch application.

        Args:
            registry: The registry of functions to be serviced.

            verification_key: The verification key to use for requests.
        """
        super().__init__()
        self.registry = registry
        self.verification_key = parse_verification_key(verification_key)
        self.add_routes(
            [
                web.post(
                    "/dispatch.sdk.v1.FunctionService/Run", self.handle_run_request
                ),
            ]
        )

    def __call__(self, request, client_address, server):
        return FunctionServiceHTTPRequestHandler(
            request,
            client_address,
            server,
            registry=self.registry,
            verification_key=self.verification_key,
        )

    async def handle_run_request(self, request: web.Request) -> web.Response:
        return await function_service_run_handler(
            request, self.registry, self.verification_key
        )


class Server:
    host: str
    port: int
    app: web.Application

    _runner: web.AppRunner
    _site: web.TCPSite

    def __init__(self, host: str, port: int, app: web.Application):
        self.host = host
        self.port = port
        self.app = app

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def start(self):
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        if self.port == 0:
            assert self._site._server is not None
            assert hasattr(self._site._server, "sockets")
            sockets = self._site._server.sockets
            self.port = sockets[0].getsockname()[1] if sockets else 0

    async def stop(self):
        await self._site.stop()
        await self._runner.cleanup()


def make_error_response_body(code: str, message: str) -> bytes:
    return f'{{"code":"{code}","message":"{message}"}}'.encode()


def make_error_response(status: int, code: str, message: str) -> web.Response:
    body = make_error_response_body(code, message)
    return web.Response(status=status, content_type="application/json", body=body)


def make_error_response_invalid_argument(message: str) -> web.Response:
    return make_error_response(400, "invalid_argument", message)


def make_error_response_not_found(message: str) -> web.Response:
    return make_error_response(404, "not_found", message)


def make_error_response_unauthenticated(message: str) -> web.Response:
    return make_error_response(401, "unauthenticated", message)


def make_error_response_permission_denied(message: str) -> web.Response:
    return make_error_response(403, "permission_denied", message)


def make_error_response_internal(message: str) -> web.Response:
    return make_error_response(500, "internal", message)


async def function_service_run_handler(
    request: web.Request,
    function_registry: Registry,
    verification_key: Optional[Ed25519PublicKey],
) -> web.Response:
    valid, reason = validate_content_length(request.content_length or 0)
    if not valid:
        return make_error_response_invalid_argument(reason)

    data: bytes = await request.read()
    try:
        content = await function_service_run(
            str(request.url),
            request.method,
            dict(request.headers),
            data,
            function_registry,
            verification_key,
        )
    except FunctionServiceError as e:
        return make_error_response(e.status, e.code, e.message)
    return web.Response(status=200, content_type="application/proto", body=content)


async def function_service_run(
    url: str,
    method: str,
    headers: Mapping[str, str],
    data: bytes,
    function_registry: Registry,
    verification_key: Optional[Ed25519PublicKey],
) -> bytes:
    logger.debug("handling run request with %d byte body", len(data))

    if verification_key is None:
        logger.debug("skipping request signature verification")
    else:
        signed_request = Request(
            method=method,
            url=url,
            headers=CaseInsensitiveDict(headers),
            body=data,
        )
        max_age = timedelta(minutes=5)
        try:
            verify_request(signed_request, verification_key, max_age)
        except ValueError as e:
            raise FunctionServiceError(401, "unauthenticated", str(e))
        except InvalidSignature as e:
            # The http_message_signatures package sometimes wraps does not
            # attach a message to the exception, so we set a default to
            # have some context about the reason for the error.
            message = str(e) or "invalid signature"
            raise FunctionServiceError(403, "permission_denied", message)

    req = function_pb.RunRequest.FromString(data)
    if not req.function:
        raise FunctionServiceError(400, "invalid_argument", "function is required")

    try:
        func = function_registry.functions[req.function]
    except KeyError:
        logger.debug("function '%s' not found", req.function)
        raise FunctionServiceError(
            404, "not_found", f"function '{req.function}' does not exist"
        )

    input = Input(req)
    logger.info("running function '%s'", req.function)

    try:
        output = await func._primitive_call(input)
    except Exception:
        # This indicates that an exception was raised in a primitive
        # function. Primitive functions must catch exceptions, categorize
        # them in order to derive a Status, and then return a RunResponse
        # that carries the Status and the error details. A failure to do
        # so indicates a problem, and we return a 500 rather than attempt
        # to catch and categorize the error here.
        logger.error("function '%s' fatal error", req.function, exc_info=True)
        raise FunctionServiceError(
            500, "internal", f"function '{req.function}' fatal error"
        )

    response = output._message
    status = Status(response.status)

    if req.dispatch_id not in _calls:
        _calls[req.dispatch_id] = asyncio.Future()

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
            call_result = CallResult._from_proto(result)
            call_future = _calls[req.dispatch_id]
            if call_result.error is not None:
                call_result.error.status = Status(response.status)
                if not call_result.error.status.temporary:
                    call_future.set_exception(call_result.error.to_exception())
            else:
                call_future.set_result(call_result.output)
            if result.HasField("output"):
                logger.debug("function '%s' exiting with output value", req.function)
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
    return response.SerializeToString()
