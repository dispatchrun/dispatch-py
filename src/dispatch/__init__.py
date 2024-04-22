"""The Dispatch SDK for Python."""

from __future__ import annotations

import os
from concurrent import futures
from contextlib import contextmanager
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
from dispatch.sdk.v1 import function_pb2_grpc as function_grpc
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


def run(init: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run the default dispatch server on the given port. The default server
    uses a function registry where functions tagged by the `@dispatch.function`
    decorator are registered.

    This function is intended to be used with the `dispatch` CLI tool, which
    automatically configures environment variables to connect the local server
    to the Dispatch bridge API.

    Args:
        entrypoint: The entrypoint function to run. Defaults to a no-op function.

        args: Positional arguments to pass to the entrypoint.

        kwargs: Keyword arguments to pass to the entrypoint.

    Returns:
        The return value of the entrypoint function.
    """
    with serve():
        return init(*args, **kwargs)


@contextmanager
def serve(address: str = os.environ.get("DISPATCH_ENDPOINT_ADDR", "localhost:8000")):
    """Returns a context manager managing the operation of a Disaptch server
    running on the given address. The server is initialized before the context
    manager yields, then runs forever until the the program is interrupted.

    Args:
        address: The address to bind the server to. Defaults to the value of the
          DISPATCH_ENDPOINT_ADDR environment variable, or 'localhost:8000' if it
          wasn't set.
    """
    parsed_url = urlsplit("//" + address)
    server_address = (parsed_url.hostname or "", parsed_url.port or 0)
    server = ThreadingHTTPServer(server_address, Dispatch(default_registry()))
    try:
        yield server
        server.serve_forever()
    finally:
        server.server_close()
