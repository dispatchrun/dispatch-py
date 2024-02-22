from __future__ import annotations

import inspect
import logging
from functools import wraps
from types import FunctionType
from typing import Any, Callable, Dict, TypeAlias

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


# https://stackoverflow.com/questions/653368/how-to-create-a-decorator-that-can-be-used-either-with-or-without-parameters
def decorator(f):
    """This decorator is intended to declare decorators that can be used with
    or without parameters. If the decorated function is called with a single
    callable argument, it is assumed to be a function and the decorator is
    applied to it. Otherwise, the decorator is called with the arguments
    provided and the result is returned.
    """

    @wraps(f)
    def method(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return f(self, args[0])

        def wrapper(func):
            return f(self, func, *args, **kwargs)

        return wrapper

    return method


class Function:
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
        func: Callable,
        coroutine: bool = False,
    ):
        self._endpoint = endpoint
        self._client = client
        self._name = name
        self._primitive_func = primitive_func
        # FIXME: is there a way to decorate the function at the definition
        #  without making it a class method?
        self._func = durable(self._call_async) if coroutine else func

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

    def dispatch(self, *args: Any, **kwargs: Any) -> DispatchID:
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

    async def _call_async(self, *args, **kwargs) -> Any:
        """Asynchronously call the function from a @dispatch.function."""
        return await dispatch.coroutine.call(
            self.build_call(*args, **kwargs, correlation_id=None)
        )

    def build_call(
        self, *args: Any, correlation_id: int | None = None, **kwargs: Any
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

    @decorator
    def function(self, func: Callable) -> Function:
        """Returns a decorator that registers functions."""
        return self._register_function(func)

    @decorator
    def primitive_function(self, func: Callable) -> Function:
        """Returns a decorator that registers primitive functions."""
        return self._register_primitive_function(func)

    def _register_function(self, func: Callable) -> Function:
        if inspect.iscoroutinefunction(func):
            return self._register_coroutine(func)

        logger.info("registering function: %s", func.__qualname__)

        # Register the function with the experimental.durable package, in case
        # it's referenced from a @dispatch.coroutine.
        func = durable(func)

        @wraps(func)
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

        return self._register(primitive_func, func, coroutine=False)

    def _register_coroutine(self, func: Callable) -> Function:
        logger.info("registering coroutine: %s", func.__qualname__)

        func = durable(func)

        @wraps(func)
        def primitive_func(input: Input) -> Output:
            return OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{func.__qualname__}_primitive"
        primitive_func = durable(primitive_func)

        return self._register(primitive_func, func, coroutine=True)

    def _register_primitive_function(self, func: PrimitiveFunctionType) -> Function:
        logger.info("registering primitive function: %s", func.__qualname__)
        return self._register(func, func, coroutine=inspect.iscoroutinefunction(func))

    def _register(
        self, primitive_func: PrimitiveFunctionType, func: Callable, coroutine: bool
    ) -> Function:
        name = func.__qualname__
        if name in self._functions:
            raise ValueError(
                f"function or coroutine already registered with name '{name}'"
            )
        wrapped_func = Function(
            self._endpoint, self._client, name, primitive_func, func, coroutine
        )
        self._functions[name] = wrapped_func
        return wrapped_func

    def set_client(self, client: Client):
        """Set the Client instance used to dispatch calls to local functions."""
        self._client = client
        for fn in self._functions.values():
            fn._client = client
