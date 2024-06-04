from typing import Optional, Union

from aiohttp import web

from dispatch.function import Registry
from dispatch.http import (
    FunctionServiceError,
    function_service_run,
    make_error_response_body,
)
from dispatch.signature import Ed25519PublicKey, parse_verification_key


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

    async def handle_run_request(self, request: web.Request) -> web.Response:
        return await function_service_run_handler(
            request, self.registry, self.verification_key
        )


class Server:
    host: str
    port: int
    app: Dispatch

    _runner: web.AppRunner
    _site: web.TCPSite

    def __init__(self, host: str, port: int, app: Dispatch):
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

    async def stop(self):
        await self._site.stop()
        await self._runner.cleanup()


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
    content_length = request.content_length
    if content_length is None or content_length == 0:
        return make_error_response_invalid_argument("content length is required")
    if content_length < 0:
        return make_error_response_invalid_argument("content length is negative")
    if content_length > 16_000_000:
        return make_error_response_invalid_argument("content length is too large")

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
