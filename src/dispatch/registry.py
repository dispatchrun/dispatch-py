import logging
from types import FunctionType
from typing import Any, Callable, Dict, TypeAlias

from dispatch import Client, DispatchID
from dispatch.function import Error, Function, Input, Output, Status
from dispatch.status import status_for_error

logger = logging.getLogger(__name__)


PrimitiveFunctionType: TypeAlias = Callable[[Input], Output]
"""A primitive function is a function that accepts a dispatch.function.Input
and unconditionally returns a dispatch.function.Output. It must not raise
exceptions.
"""


class FunctionRegistry:
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

        def primitive_func(input: Input) -> Output:
            try:
                args, kwargs = input.arguments()
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
        wrapped_func = Function(self._endpoint, name, func)
        self._functions[name] = wrapped_func
        return wrapped_func

    def call(self, fn: Function | str, input: Any = None) -> DispatchID:
        """Dispatch a call to a local function.

        The registry must be initialize with a client for this call facility
        to be available.

        Args:
            fn: The function to dispatch a call to.
            input: Input to the function.

        Returns:
            DispatchID: ID of the dispatched call.

        Raises:
            RuntimeError: if a Dispatch client has not been configured.
            ValueError: if the function has not been registered.
        """
        if self._client is None:
            raise RuntimeError(
                "Dispatch client has not been configured (api_key not provided)"
            )

        if isinstance(fn, Function):
            fn = fn.name

        try:
            wrapped_func = self._functions[fn]
        except KeyError:
            raise ValueError(
                f"function {fn} has not been registered (via @dispatch.function)"
            )

        [dispatch_id] = self._client.dispatch([wrapped_func.call_with(input)])
        return dispatch_id
