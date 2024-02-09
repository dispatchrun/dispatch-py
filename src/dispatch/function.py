from __future__ import annotations

import functools
import logging
from types import FunctionType
from typing import Any, Callable, Dict, TypeAlias

from dispatch.client import Client
from dispatch.id import DispatchID
from dispatch.proto import Call, Error, Input, Output, _Arguments
from dispatch.status import Status

logger = logging.getLogger(__name__)


class Function:
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    def __init__(
        self,
        endpoint: str,
        client: Client | None,
        name: str,
        func: Callable[[Input], Output],
    ):
        self._endpoint = endpoint
        self._client = client
        self._name = name
        self._func = func

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

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
        return self.primitive_dispatch(_Arguments(list(args), kwargs))

    def primitive_dispatch(self, input: Any = None) -> DispatchID:
        """Dispatch a primitive call.

        The Registry this function was registered with must be initialized
        with a Client / api_key for this call facility to be available.

        Args:
            input: Input to the function.

        Returns:
            DispatchID: ID of the dispatched call.

        Raises:
            RuntimeError: if a Dispatch client has not been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "Dispatch Client has not been configured (api_key not provided)"
            )

        [dispatch_id] = self._client.dispatch([self.primitive_call_with(input)])
        return dispatch_id

    def call_with(self, *args, correlation_id: int | None = None, **kwargs) -> Call:
        """Create a Call for this function with the provided input. Useful to
        generate calls when polling.

        Args:
            *args: Positional arguments for the function.
            correlation_id: optional arbitrary integer the caller can use to
              match this call to a call result.
            **kwargs: Keyword arguments for the function.

        Returns:
            Call: can be passed to Output.poll().
        """
        return self.primitive_call_with(
            _Arguments(list(args), kwargs), correlation_id=correlation_id
        )

    def primitive_call_with(
        self, input: Any, correlation_id: int | None = None
    ) -> Call:
        """Create a Call for this function with the provided input. Useful to
        generate calls when polling.

        Args:
            input: any pickle-able Python value that will be passed as input to
              this function.
            correlation_id: optional arbitrary integer the caller can use to
              match this call to a call result.

        Returns:
            Call: can be passed to Output.poll().
        """
        return Call(
            correlation_id=correlation_id,
            endpoint=self.endpoint,
            function=self.name,
            input=input,
        )


PrimitiveFunctionType: TypeAlias = Callable[[Input], Output]
"""A primitive function is a function that accepts a dispatch.function.Input
and unconditionally returns a dispatch.function.Output. It must not raise
exceptions.
"""


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
        return self._register

    def primitive_function(self) -> Callable[[PrimitiveFunctionType], Function]:
        """Returns a decorator that registers primitive functions."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._primitive_register

    def _register(self, func: FunctionType) -> Function:
        """Register a function with the Dispatch programmable endpoints.

        Args:
            func: The function to register.

        Returns:
            Function: A registered Dispatch Function.

        Raises:
            ValueError: If the function is already registered.
        """

        @functools.wraps(func)
        def primitive_func(input: Input) -> Output:
            try:
                args, kwargs = input.input_arguments()
            except ValueError:
                return Output.error(
                    Error(
                        Status.INVALID_ARGUMENT,
                        "ValueError",
                        "incorrect input for function",
                    )
                )
            try:
                raw_output = func(*args, **kwargs)
            except Exception as e:
                return Output.error(Error.from_exception(e))
            else:
                return Output.value(raw_output)

        return self._primitive_register(primitive_func)

    def _primitive_register(self, func: PrimitiveFunctionType) -> Function:
        """Register a primitive function with the Dispatch programmable endpoints.

        Args:
            func: The function to register.

        Returns:
            Function: A registered Dispatch Function.

        Raises:
            ValueError: If the function is already registered.
        """
        name = func.__qualname__
        logger.info("registering function '%s'", name)
        if name in self._functions:
            raise ValueError(f"Function {name} already registered")
        wrapped_func = Function(self._endpoint, self._client, name, func)
        self._functions[name] = wrapped_func
        return wrapped_func
