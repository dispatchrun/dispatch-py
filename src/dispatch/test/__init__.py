import asyncio
import unittest
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Coroutine, Optional, TypeVar, overload

import aiohttp
from aiohttp import web
from google.protobuf.timestamp_pb2 import Timestamp

import dispatch.experimental.durable.registry
from dispatch.function import Client as BaseClient
from dispatch.function import Registry as BaseRegistry
from dispatch.http import Dispatch
from dispatch.http import Server as BaseServer
from dispatch.sdk.v1.call_pb2 import Call, CallResult
from dispatch.sdk.v1.dispatch_pb2 import DispatchRequest, DispatchResponse
from dispatch.sdk.v1.error_pb2 import Error
from dispatch.sdk.v1.function_pb2 import RunRequest, RunResponse
from dispatch.sdk.v1.poll_pb2 import PollResult
from dispatch.sdk.v1.status_pb2 import STATUS_OK

from .client import EndpointClient
from .server import DispatchServer
from .service import DispatchService

__all__ = [
    "EndpointClient",
    "DispatchServer",
    "DispatchService",
    "function",
    "method",
    "main",
    "run",
    "Client",
    "Server",
    "Service",
    "Registry",
    "DISPATCH_ENDPOINT_URL",
    "DISPATCH_API_URL",
    "DISPATCH_API_KEY",
]

R = TypeVar("R", bound=BaseRegistry)
T = TypeVar("T")

DISPATCH_ENDPOINT_URL = "http://localhost:0"
DISPATCH_API_URL = "http://localhost:0"
DISPATCH_API_KEY = "916CC3D280BB46DDBDA984B3DD10059A"


class Client(BaseClient):
    def session(self) -> aiohttp.ClientSession:
        # Use an individual sessionn in the test client instead of the default
        # global session from dispatch.http so we don't crash when a different
        # event loop is employed in each test.
        return aiohttp.ClientSession()


class Registry(BaseRegistry):
    def __init__(self):
        # placeholder values to initialize the base class prior to binding
        # random ports.
        super().__init__(
            endpoint=DISPATCH_ENDPOINT_URL,
            api_url=DISPATCH_API_URL,
            api_key=DISPATCH_API_KEY,
        )


class Server(BaseServer):
    def __init__(self, app: web.Application):
        super().__init__("localhost", 0, app)

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"


class Service(web.Application):
    tasks: dict[str, asyncio.Task[CallResult]]

    def __init__(self):
        super().__init__()
        self.dispatch_ids = (str(i) for i in range(2**32 - 1))
        self.tasks = {}
        self.add_routes(
            [
                web.post(
                    "/dispatch.sdk.v1.DispatchService/Dispatch",
                    self.handle_dispatch_request,
                ),
                web.post(
                    "/dispatch.sdk.v1.DispatchService/Wait",
                    self.handle_wait_request,
                ),
            ]
        )

    async def authenticate(self, request: web.Request):
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            raise web.HTTPUnauthorized(text="missing authentication token")

        token = auth[len("Bearer ") :]
        if token != DISPATCH_API_KEY:
            raise web.HTTPUnauthorized(text="invalid authentication token")

    async def handle_dispatch_request(self, request: web.Request):
        await self.authenticate(request)
        req = DispatchRequest.FromString(await request.read())
        async with aiohttp.ClientSession() as session:
            res = await self.dispatch(session, req)
        return web.Response(
            content_type="application/proto", body=res.SerializeToString()
        )

    async def handle_wait_request(self, request: web.Request):
        await self.authenticate(request)
        req = str(await request.read(), "utf-8")
        res = await self.wait(req)
        return web.Response(
            content_type="application/proto", body=res.SerializeToString()
        )

    async def dispatch(
        self, session: aiohttp.ClientSession, req: DispatchRequest
    ) -> DispatchResponse:
        dispatch_ids = [next(self.dispatch_ids) for _ in req.calls]

        for call, dispatch_id in zip(req.calls, dispatch_ids):
            self.tasks[dispatch_id] = asyncio.create_task(
                self.call(session, call, dispatch_id)
            )

        return DispatchResponse(dispatch_ids=dispatch_ids)

    # TODO: add to protobuf definitions
    async def wait(self, dispatch_id: str) -> CallResult:
        return await self.tasks[dispatch_id]

    async def call(
        self,
        session: aiohttp.ClientSession,
        call: Call,
        dispatch_id: str,
        parent_dispatch_id: Optional[str] = None,
        root_dispatch_id: Optional[str] = None,
    ) -> CallResult:
        root_dispatch_id = root_dispatch_id or dispatch_id

        now = datetime.now()
        exp = now + (
            timedelta(
                seconds=call.expiration.seconds,
                microseconds=call.expiration.nanos // 1000,
            )
            if call.expiration
            else timedelta(seconds=60)
        )

        creation_time = Timestamp()
        creation_time.FromDatetime(now)

        expiration_time = Timestamp()
        expiration_time.FromDatetime(exp)

        req = RunRequest(
            function=call.function,
            input=call.input,
            creation_time=creation_time,
            expiration_time=expiration_time,
            dispatch_id=dispatch_id,
            parent_dispatch_id=parent_dispatch_id,
            root_dispatch_id=root_dispatch_id,
        )

        endpoint = call.endpoint
        while True:
            res = await self.run(session, endpoint, req)

            if res.status != STATUS_OK:
                # TODO: emulate retries etc...
                return CallResult(
                    dispatch_id=dispatch_id,
                    error=Error(type="status", message=str(res.status)),
                )

            if res.exit:
                if res.exit.tail_call:
                    req.function = res.exit.tail_call.function
                    req.input = res.exit.tail_call.input
                    req.poll_result = None  # type: ignore
                    continue
                return CallResult(
                    dispatch_id=dispatch_id,
                    output=res.exit.result.output,
                    error=res.exit.result.error,
                )

            for call in res.poll.calls:
                if not call.endpoint:
                    call.endpoint = endpoint

            # TODO: enforce poll limits
            req.input = None  # type: ignore
            req.poll_result = PollResult(
                coroutine_state=res.poll.coroutine_state,
                results=await asyncio.gather(
                    *[
                        self.call(session, call, dispatch_id)
                        for call, dispatch_id in zip(
                            res.poll.calls, next(self.dispatch_ids)
                        )
                    ]
                ),
            )

    async def run(
        self, session: aiohttp.ClientSession, endpoint: str, req: RunRequest
    ) -> RunResponse:
        async with await session.post(
            f"{endpoint}/dispatch.sdk.v1.FunctionService/Run",
            data=req.SerializeToString(),
        ) as response:
            return RunResponse.FromString(await response.read())


async def main(reg: R, fn: Callable[[R], Coroutine[Any, Any, None]]) -> None:
    api = Service()
    app = Dispatch(reg)
    try:
        async with Server(api) as backend:
            async with Server(app) as server:
                # Here we break through the abstraction layers a bit, it's not
                # ideal but it works for now.
                reg.client.api_url.value = backend.url
                reg.endpoint = server.url
                await fn(reg)
    finally:
        # TODO: let's figure out how to get rid of this global registry
        # state at some point, which forces tests to be run sequentially.
        dispatch.experimental.durable.registry.clear_functions()


def run(reg: R, fn: Callable[[R], Coroutine[Any, Any, None]]) -> None:
    return asyncio.run(main(reg, fn))


def function(fn: Callable[[Registry], Coroutine[Any, Any, None]]) -> Callable[[], None]:
    @wraps(fn)
    def wrapper():
        return run(Registry(), fn)

    return wrapper


def method(
    fn: Callable[[T, Registry], Coroutine[Any, Any, None]]
) -> Callable[[T], None]:
    @wraps(fn)
    def wrapper(self: T):
        return run(Registry(), lambda reg: fn(self, reg))

    return wrapper
