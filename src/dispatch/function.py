from __future__ import annotations

import inspect
import logging
import os
from functools import wraps
from types import CoroutineType
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    ParamSpec,
    TypeAlias,
    TypeVar,
    overload,
)
from urllib.parse import urlparse

import grpc

import dispatch.coroutine
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
from dispatch.experimental.durable import durable
from dispatch.id import DispatchID
from dispatch.proto import Arguments, Call, Error, Input, Output
from dispatch.scheduler import OneShotScheduler

logger = logging.getLogger(__name__)


PrimitiveFunctionType: TypeAlias = Callable[[Input], Output]
"""A primitive function is a function that accepts a dispatch.proto.Input
and unconditionally returns a dispatch.proto.Output. It must not raise
exceptions.
"""


DEFAULT_API_URL = "https://api.dispatch.run"


class PrimitiveFunction:
    __slots__ = ("_endpoint", "_client", "_name", "_primitive_func")

    def __init__(
        self,
        endpoint: str,
        client: Client,
        name: str,
        primitive_func: PrimitiveFunctionType,
    ):
        self._endpoint = endpoint
        self._client = client
        self._name = name
        self._primitive_func = primitive_func

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def name(self) -> str:
        return self._name

    def _primitive_call(self, input: Input) -> Output:
        return self._primitive_func(input)

    def _primitive_dispatch(self, input: Any = None) -> DispatchID:
        [dispatch_id] = self._client.dispatch([self._build_primitive_call(input)])
        return dispatch_id

    def _build_primitive_call(
        self, input: Any, correlation_id: int | None = None
    ) -> Call:
        return Call(
            correlation_id=correlation_id,
            endpoint=self.endpoint,
            function=self.name,
            input=input,
        )


P = ParamSpec("P")
T = TypeVar("T")


class Function(PrimitiveFunction, Generic[P, T]):
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    __slots__ = ("_func_indirect",)

    def __init__(
        self,
        endpoint: str,
        client: Client,
        name: str,
        primitive_func: PrimitiveFunctionType,
        func: Callable,
    ):
        PrimitiveFunction.__init__(self, endpoint, client, name, primitive_func)

        self._func_indirect: Callable[P, Coroutine[Any, Any, T]] = durable(
            self._call_async
        )

    async def _call_async(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return await dispatch.coroutine.call(
            self.build_call(*args, **kwargs, correlation_id=None)
        )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, T]:
        """Call the function asynchronously (through Dispatch), and return a
        coroutine that can be awaited to retrieve the call result."""
        return self._func_indirect(*args, **kwargs)

    def dispatch(self, *args: P.args, **kwargs: P.kwargs) -> DispatchID:
        """Dispatch an asynchronous call to the function without
        waiting for a result.

        The Registry this function was registered with must be initialized
        with a Client / api_key for this call facility to be available.

        Args:
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            DispatchID: ID of the dispatched call.

        Raises:
            RuntimeError: if a Dispatch client has not been configured.
        """
        return self._primitive_dispatch(Arguments(args, kwargs))

    def build_call(
        self, *args: P.args, correlation_id: int | None = None, **kwargs: P.kwargs
    ) -> Call:
        """Create a Call for this function with the provided input. Useful to
        generate calls when using the Client.

        Args:
            *args: Positional arguments for the function.
            correlation_id: optional arbitrary integer the caller can use to
                match this call to a call result.
            **kwargs: Keyword arguments for the function.

        Returns:
            Call: can be passed to Client.dispatch.
        """
        return self._build_primitive_call(
            Arguments(args, kwargs), correlation_id=correlation_id
        )


class Registry:
    """Registry of local functions."""

    __slots__ = ("_functions", "_endpoint", "_client")

    def __init__(self, endpoint: str, client: Client):
        """Initialize a local function registry.

        Args:
            endpoint: URL of the endpoint that the function is accessible from.
            client: Client for the Dispatch API. Used to dispatch calls to
                local functions.
        """
        self._functions: Dict[str, PrimitiveFunction] = {}
        self._endpoint = endpoint
        self._client = client

    @overload
    def function(self, func: Callable[P, Coroutine[Any, Any, T]]) -> Function[P, T]: ...

    @overload
    def function(self, func: Callable[P, T]) -> Function[P, T]: ...

    def function(self, func):
        """Decorator that registers functions."""
        if not inspect.iscoroutinefunction(func):
            logger.info("registering function: %s", func.__qualname__)
            return self._register_function(func)

        logger.info("registering coroutine: %s", func.__qualname__)
        return self._register_coroutine(func)

    def _register_function(self, func: Callable[P, T]) -> Function[P, T]:
        func = durable(func)

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return func(*args, **kwargs)

        async_wrapper.__qualname__ = f"{func.__qualname__}_async"

        return self._register_coroutine(async_wrapper)

    def _register_coroutine(
        self, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Function[P, T]:
        name = func.__qualname__
        logger.info("registering coroutine: %s", name)

        func = durable(func)

        @wraps(func)
        def primitive_func(input: Input) -> Output:
            return OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{name}_primitive"
        primitive_func = durable(primitive_func)

        wrapped_func = Function[P, T](
            self._endpoint, self._client, name, primitive_func, func
        )
        self._register(name, wrapped_func)
        return wrapped_func

    def primitive_function(
        self, primitive_func: PrimitiveFunctionType
    ) -> PrimitiveFunction:
        """Decorator that registers primitive functions."""
        name = primitive_func.__qualname__
        logger.info("registering primitive function: %s", name)
        wrapped_func = PrimitiveFunction(
            self._endpoint, self._client, name, primitive_func
        )
        self._register(name, wrapped_func)
        return wrapped_func

    def _register(self, name: str, wrapped_func: PrimitiveFunction):
        if name in self._functions:
            raise ValueError(f"function already registered with name '{name}'")
        self._functions[name] = wrapped_func

    def set_client(self, client: Client):
        """Set the Client instance used to dispatch calls to local functions."""
        self._client = client
        for fn in self._functions.values():
            fn._client = client


class Client:
    """Client for the Dispatch API."""

    __slots__ = ("api_url", "api_key", "_stub", "api_key_from")

    def __init__(self, api_key: None | str = None, api_url: None | str = None):
        """Create a new Dispatch client.

        Args:
            api_key: Dispatch API key to use for authentication. Uses the value of
                the DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use. Uses the value of the
                DISPATCH_API_URL environment variable if set, otherwise
                defaults to the public Dispatch API (DEFAULT_API_URL).

        Raises:
            ValueError: if the API key is missing.
        """

        if api_key:
            self.api_key_from = "api_key"
        else:
            self.api_key_from = "DISPATCH_API_KEY"
            api_key = os.environ.get("DISPATCH_API_KEY")
        if not api_key:
            raise ValueError(
                "missing API key: set it with the DISPATCH_API_KEY environment variable"
            )

        if not api_url:
            api_url = os.environ.get("DISPATCH_API_URL", DEFAULT_API_URL)
        if not api_url:
            raise ValueError(
                "missing API URL: set it with the DISPATCH_API_URL environment variable"
            )

        logger.debug("initializing client for Dispatch API at URL %s", api_url)
        self.api_url = api_url
        self.api_key = api_key
        self._init_stub()

    def __getstate__(self):
        return {"api_url": self.api_url, "api_key": self.api_key}

    def __setstate__(self, state):
        self.api_url = state["api_url"]
        self.api_key = state["api_key"]
        self._init_stub()

    def _init_stub(self):
        result = urlparse(self.api_url)
        match result.scheme:
            case "http":
                creds = grpc.local_channel_credentials()
            case "https":
                creds = grpc.ssl_channel_credentials()
            case _:
                raise ValueError(f"Invalid API scheme: '{result.scheme}'")

        call_creds = grpc.access_token_call_credentials(self.api_key)
        creds = grpc.composite_channel_credentials(creds, call_creds)
        channel = grpc.secure_channel(result.netloc, creds)

        self._stub = dispatch_grpc.DispatchServiceStub(channel)

    def batch(self) -> Batch:
        """Returns a Batch instance that can be used to build
        a set of calls to dispatch."""
        return Batch(self)

    def dispatch(self, calls: Iterable[Call]) -> list[DispatchID]:
        """Dispatch function calls.

        Args:
            calls: Calls to dispatch.

        Returns:
            Identifiers for the function calls, in the same order as the inputs.
        """
        calls_proto = [c._as_proto() for c in calls]
        logger.debug("dispatching %d function call(s)", len(calls_proto))
        req = dispatch_pb.DispatchRequest(calls=calls_proto)

        try:
            resp = self._stub.Dispatch(req)
        except grpc.RpcError as e:
            status_code = e.code()
            match status_code:
                case grpc.StatusCode.UNAUTHENTICATED:
                    raise PermissionError(
                        f"Dispatch received an invalid authentication token (check {self.api_key_from} is correct)"
                    ) from e
            raise

        dispatch_ids = [DispatchID(x) for x in resp.dispatch_ids]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "dispatched %d function call(s): %s",
                len(calls_proto),
                ", ".join(dispatch_ids),
            )
        return dispatch_ids


class Batch:
    """A batch of calls to dispatch."""

    __slots__ = ("client", "calls")

    def __init__(self, client: Client):
        self.client = client
        self.calls: list[Call] = []

    def add(self, func: Function[P, T], *args: P.args, **kwargs: P.kwargs) -> Batch:
        """Add a call to the specified function to the batch."""
        return self.add_call(func.build_call(*args, correlation_id=None, **kwargs))

    def add_call(self, call: Call) -> Batch:
        """Add a Call to the batch."""
        self.calls.append(call)
        return self

    def dispatch(self) -> list[DispatchID]:
        """Dispatch dispatches the calls asynchronously.

        The batch is reset when the calls are dispatched successfully.

        Returns:
            Identifiers for the function calls, in the same order they
            were added.
        """
        if not self.calls:
            return []

        dispatch_ids = self.client.dispatch(self.calls)
        self.reset()
        return dispatch_ids

    def reset(self):
        """Reset the batch."""
        self.calls = []
