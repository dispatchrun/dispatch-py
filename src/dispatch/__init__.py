"""The Dispatch SDK for Python."""

from __future__ import annotations

import asyncio
import os
from http.server import ThreadingHTTPServer
from typing import Any, Callable, Coroutine, Optional, TypeVar, overload
from urllib.parse import urlsplit

from typing_extensions import ParamSpec, TypeAlias

import dispatch.integrations
from dispatch.coroutine import all, any, call, gather, race
from dispatch.function import AsyncFunction as Function
from dispatch.function import (
    Batch,
    Client,
    ClientError,
    Registry,
    Reset,
    default_registry,
)
from dispatch.http import Dispatch, Server
from dispatch.id import DispatchID
from dispatch.proto import Call, Error, Input, Output
from dispatch.status import Status

__all__ = [
    "Call",
    "Client",
    "ClientError",
    "DispatchID",
    "Error",
    "Input",
    "Output",
    "Registry",
    "Reset",
    "Status",
    "all",
    "any",
    "call",
    "function",
    "gather",
    "race",
    "run",
    "serve",
]


P = ParamSpec("P")
T = TypeVar("T")


@overload
def function(func: Callable[P, Coroutine[Any, Any, T]]) -> Function[P, T]: ...


@overload
def function(func: Callable[P, T]) -> Function[P, T]: ...


def function(func):
    return default_registry().function(func)


async def main(coro: Coroutine[Any, Any, T], addr: Optional[str] = None) -> T:
    """Entrypoint of dispatch applications. This function creates a new
    Dispatch server and runs the provided coroutine in the server's event loop.

    Programs typically don't use this function directly, unless they manage
    their own event loop. Most of the time, the `run` function is a more
    convenient way to run a dispatch application.

    Args:
        coro: The coroutine to run as the entrypoint, the function returns
            when the coroutine returns.

        addr: The address to bind the server to. If not provided, the server
            will bind to the address specified by the `DISPATCH_ENDPOINT_ADDR`

    Returns:
        The value returned by the coroutine.
    """
    address = addr or str(os.environ.get("DISPATCH_ENDPOINT_ADDR")) or "localhost:8000"
    parsed_url = urlsplit("//" + address)

    host = parsed_url.hostname or ""
    port = parsed_url.port or 0

    reg = default_registry()
    app = Dispatch(reg)

    async with Server(host, port, app) as server:
        return await coro


def run(coro: Coroutine[Any, Any, T], addr: Optional[str] = None) -> T:
    """Run the default dispatch server. The default server uses a function
    registry where functions tagged by the `@dispatch.function` decorator are
    registered.

    This function is intended to be used with the `dispatch` CLI tool, which
    automatically configures environment variables to connect the local server
    to the Dispatch bridge API.

    Args:
        coro: The coroutine to run as the entrypoint, the function returns
            when the coroutine returns.

        addr: The address to bind the server to. If not provided, the server
            will bind to the address specified by the `DISPATCH_ENDPOINT_ADDR`
            environment variable. If the environment variable is not set, the
            server will bind to `localhost:8000`.

    Returns:
        The value returned by the coroutine.
    """
    return asyncio.run(main(coro, addr))


def run_forever():
    """Run the default dispatch server forever."""
    return run(asyncio.Event().wait())


def batch() -> Batch:
    """Create a new batch object."""
    return default_registry().batch()
