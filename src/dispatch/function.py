from __future__ import annotations

import functools
import inspect
import logging
from types import FunctionType
from typing import Any, Callable, Dict, TypeAlias

import dispatch.coroutine
from dispatch.client import Client
from dispatch.experimental.durable import durable
from dispatch.id import DispatchID
from dispatch.proto import Call, Error, Input, Output, _Arguments
from dispatch.scheduler import OneShotScheduler

logger = logging.getLogger(__name__)


PrimitiveFunctionType: TypeAlias = Callable[[Input], Output]
"""A primitive function is a function that accepts a dispatch.proto.Input
and unconditionally returns a dispatch.proto.Output. It must not raise
exceptions.
"""


class Function:
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    def __init__(
        self,
        endpoint: str,
        client: Client | None,
        name: str,
        primitive_func: PrimitiveFunctionType,
        func: Callable,
    ):
        self._endpoint = endpoint
        self._client = client
        self._name = name
        self._primitive_func = primitive_func
        self._func = func

        # FIXME: is there a way to decorate the function at the definition
        #  without making it a class method?
        self.call = durable(self._call_async)

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def _primitive_call(self, input: Input) -> Output:
        return self._primitive_func(input)

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def name(self) -> str:
        return self._name

    def dispatch(self, *args, **kwargs) -> DispatchID:
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
        return self._primitive_dispatch(_Arguments(list(args), kwargs))

    def _primitive_dispatch(self, input: Any = None) -> DispatchID:
        if self._client is None:
            raise RuntimeError(
                "Dispatch Client has not been configured (api_key not provided)"
            )

        [dispatch_id] = self._client.dispatch([self._build_primitive_call(input)])
        return dispatch_id

    async def _call_async(self, *args, **kwargs) -> Any:
        """Asynchronously call the function from a @dispatch.coroutine."""
        return await dispatch.coroutine.call(
            self.build_call(*args, **kwargs, correlation_id=None)
        )

    def build_call(self, *args, correlation_id: int | None = None, **kwargs) -> Call:
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
            _Arguments(list(args), kwargs), correlation_id=correlation_id
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

    def __init__(self, endpoint: str, client: Client | None):
        """Initialize a local function registry.

        Args:
            endpoint: URL of the endpoint that the function is accessible from.
            client: Optional client for the Dispatch API. If provided, calls
              to local functions can be dispatched directly.
        """
        self._functions: Dict[str, Function] = {}
        self._endpoint = endpoint
        self._client = client

    def function(self) -> Callable[[FunctionType], Function]:
        """Returns a decorator that registers functions."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._register_function

    def coroutine(self) -> Callable[[FunctionType], Function | FunctionType]:
        """Returns a decorator that registers coroutines."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._register_coroutine

    def primitive_function(self) -> Callable[[PrimitiveFunctionType], Function]:
        """Returns a decorator that registers primitive functions."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._register_primitive_function

    def _register_function(self, func: Callable) -> Function:
        if inspect.iscoroutinefunction(func):
            raise TypeError(
                "async functions must be registered via @dispatch.coroutine"
            )

        logger.info("registering function: %s", func.__qualname__)

        # Register the function with the experimental.durable package, in case
        # it's referenced from a @dispatch.coroutine.
        func = durable(func)

        def primitive_func(input: Input) -> Output:
            try:
                try:
                    args, kwargs = input.input_arguments()
                except ValueError:
                    raise ValueError("incorrect input for function")
                raw_output = func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"@dispatch.function: '{func.__name__}' raised an exception"
                )
                return Output.error(Error.from_exception(e))
            else:
                return Output.value(raw_output)

        primitive_func.__qualname__ = f"{func.__qualname__}_primitive"
        primitive_func = durable(primitive_func)

        return self._register(func, primitive_func)

    def _register_coroutine(self, func: Callable) -> Function:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"{func.__qualname__} must be an async function")

        logger.info("registering coroutine: %s", func.__qualname__)

        func = durable(func)

        @functools.wraps(func)
        def primitive_func(input: Input) -> Output:
            return OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{func.__qualname__}_primitive"
        primitive_func = durable(primitive_func)

        return self._register(func, primitive_func)

    def _register_primitive_function(self, func: PrimitiveFunctionType) -> Function:
        logger.info("registering primitive function: %s", func.__qualname__)
        return self._register(func, func)

    def _register(
        self, func: Callable, primitive_func: PrimitiveFunctionType
    ) -> Function:
        name = func.__qualname__
        if name in self._functions:
            raise ValueError(
                f"function or coroutine already registered with name '{name}'"
            )
        wrapped_func = Function(
            self._endpoint, self._client, name, primitive_func, func
        )
        self._functions[name] = wrapped_func
        return wrapped_func
