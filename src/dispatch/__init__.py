"""The Dispatch SDK for Python."""

from __future__ import annotations

import os
from concurrent import futures
from http.server import ThreadingHTTPServer
from typing import Any, Callable, Coroutine, Optional, TypeVar, overload
from urllib.parse import urlsplit

from typing_extensions import ParamSpec, TypeAlias

import dispatch.integrations
from dispatch.coroutine import all, any, call, gather, race
from dispatch.function import DEFAULT_API_URL, Client, Function, Registry, Reset
from dispatch.http import Dispatch
from dispatch.id import DispatchID
from dispatch.proto import Call, Error, Input, Output
from dispatch.status import Status

__all__ = [
    "Call",
    "Client",
    "DEFAULT_API_URL",
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

_registry: Optional[Registry] = None


def default_registry():
    global _registry
    if not _registry:
        _registry = Registry()
    return _registry


@overload
def function(func: Callable[P, Coroutine[Any, Any, T]]) -> Function[P, T]: ...


@overload
def function(func: Callable[P, T]) -> Function[P, T]: ...


def function(func):
    return default_registry().function(func)


def run(init: Optional[Callable[P, None]] = None, *args: P.args, **kwargs: P.kwargs):
    """Run the default dispatch server. The default server uses a function
    registry where functions tagged by the `@dispatch.function` decorator are
    registered.

    This function is intended to be used with the `dispatch` CLI tool, which
    automatically configures environment variables to connect the local server
    to the Dispatch bridge API.

    Args:
        init: An initialization function called after binding the server address
            but before entering the event loop to handle requests.

        args: Positional arguments to pass to the entrypoint.

        kwargs: Keyword arguments to pass to the entrypoint.

    Returns:
        The return value of the entrypoint function.
    """
    address = os.environ.get("DISPATCH_ENDPOINT_ADDR", "localhost:8000")
    parsed_url = urlsplit("//" + address)
    server_address = (parsed_url.hostname or "", parsed_url.port or 0)
    server = ThreadingHTTPServer(server_address, Dispatch(default_registry()))
    try:
        if init is not None:
            init(*args, **kwargs)
        server.serve_forever()
    finally:
        server.shutdown()
        server.server_close()
