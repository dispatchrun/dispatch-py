from __future__ import annotations

import inspect
import logging
from functools import wraps
from types import CoroutineType
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeVar,
    overload,
)

import dispatch.coroutine
from dispatch.client import Client
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


P = ParamSpec("P")
T = TypeVar("T")


class Function(Generic[P, T]):
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    __slots__ = ("_endpoint", "_client", "_name", "_primitive_func", "_func")

    def __init__(
        self,
        endpoint: str,
        client: Client,
        name: str,
        primitive_func: PrimitiveFunctionType,
        func: Callable[..., Any] | None,
    ):
        self._endpoint = endpoint
        self._client = client
        self._name = name
        self._primitive_func = primitive_func
        self._func: Callable[P, Coroutine[Any, Any, T]] | None = (
            durable(self._call_async) if func else None
        )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, T]:
        if self._func is None:
            raise ValueError("cannot call a primitive function directly")
        return self._func(*args, **kwargs)

    def _primitive_call(self, input: Input) -> Output:
        return self._primitive_func(input)

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def name(self) -> str:
        return self._name

    def dispatch(self, *args: P.args, **kwargs: P.kwargs) -> DispatchID:
        """Dispatch a call to the function.

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

    def _primitive_dispatch(self, input: Any = None) -> DispatchID:
        [dispatch_id] = self._client.dispatch([self._build_primitive_call(input)])
        return dispatch_id

    async def _call_async(self, *args: P.args, **kwargs: P.kwargs) -> T:
        """Asynchronously call the function from a @dispatch.function."""
        return await dispatch.coroutine.call(
            self.build_call(*args, **kwargs, correlation_id=None)
        )

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

    def _build_primitive_call(
        self, input: Any, correlation_id: int | None = None
    ) -> Call:
        return Call(
            correlation_id=correlation_id,
            endpoint=self.endpoint,
            function=self.name,
            input=input,
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
        self._functions: Dict[str, Function] = {}
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

    def primitive_function(self, func: PrimitiveFunctionType) -> Function:
        """Decorator that registers primitive functions."""
        return self._register_primitive_function(func)

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
        logger.info("registering coroutine: %s", func.__qualname__)

        func = durable(func)

        @wraps(func)
        def primitive_func(input: Input) -> Output:
            return OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{func.__qualname__}_primitive"
        primitive_func = durable(primitive_func)

        return self._register(primitive_func, func)

    def _register_primitive_function(
        self, primitive_func: PrimitiveFunctionType
    ) -> Function[P, T]:
        logger.info("registering primitive function: %s", primitive_func.__qualname__)
        return self._register(primitive_func, func=None)

    def _register(
        self,
        primitive_func: PrimitiveFunctionType,
        func: Callable[P, Coroutine[Any, Any, T]] | None,
    ) -> Function[P, T]:
        name = func.__qualname__ if func else primitive_func.__qualname__
        if name in self._functions:
            raise ValueError(
                f"function or coroutine already registered with name '{name}'"
            )
        wrapped_func = Function[P, T](
            self._endpoint, self._client, name, primitive_func, func
        )
        self._functions[name] = wrapped_func
        return wrapped_func

    def set_client(self, client: Client):
        """Set the Client instance used to dispatch calls to local functions."""
        self._client = client
        for fn in self._functions.values():
            fn._client = client
