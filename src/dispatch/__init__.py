"""The Dispatch SDK for Python."""
from __future__ import annotations

import os
import dispatch.integrations

from concurrent import futures
from http.server import HTTPServer
from typing import Any, Callable, Coroutine, Optional, TypeVar, overload
from typing_extensions import ParamSpec, TypeAlias
from urllib.parse import urlsplit

from dispatch.coroutine import all, any, call, gather, race
from dispatch.function import DEFAULT_API_URL, Client, Function, Registry, Reset
from dispatch.http import Dispatch
from dispatch.id import DispatchID
from dispatch.proto import Call, Error, Input, Output
from dispatch.status import Status
from dispatch.sdk.v1 import function_pb2_grpc as function_grpc

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
]


P = ParamSpec("P")
T = TypeVar("T")

_registry: Optional[Registry] = None

def _default_registry():
    global _registry
    if not _registry:
        _registry = Registry()
    return _registry

@overload
def function(func: Callable[P, Coroutine[Any, Any, T]]) -> Function[P, T]: ...

@overload
def function(func: Callable[P, T]) -> Function[P, T]: ...

def function(func):
    return _default_registry().function(func)

def run(port: str = os.environ.get("DISPATCH_ENDPOINT_ADDR", "[::]:8000")):
    """Run the default dispatch server on the given port. The default server
    uses a function registry where functions tagged by the `@dispatch.function`
    decorator are registered.

    This function is intended to be used with the `dispatch` CLI tool, which
    automatically configures environment variables to connect the local server
    to the Dispatch bridge API.

    Args:
        port: The address to bind the server to. Defaults to the value of the
          DISPATCH_ENDPOINT_ADDR environment variable, or '[::]:8000' if it
          wasn't set.
    """
    parsed_url = urlsplit('//' + port)
    server_address = (parsed_url.hostname, parsed_url.port)
    server = HTTPServer(server_address, Dispatch(_default_registry()))
    server.serve_forever()

