import logging
from types import FunctionType
from typing import Any, Callable, Dict

import dispatch.function
from dispatch import Client, DispatchID

logger = logging.getLogger(__name__)


class FunctionRegistry:
    """Registry of local functions."""

    def __init__(self, endpoint: str, client: Client | None):
        """Initialize a local function registry.

        Args:
            endpoint: URL of the endpoint that the function is accessible from.
            client: Optional client for the Dispatch API. If provided, calls
              to local functions can be dispatched directly.
        """
        self._functions: Dict[str, dispatch.function.Function] = {}
        self._endpoint = endpoint
        self._client = client

    def function(self):
        """Returns a decorator that registers functions."""

        def wrap(func: Callable[[dispatch.function.Input], dispatch.function.Output]):
            """Register a function with the Dispatch programmable endpoints.

            Args:
                func: The function to register.

            Raises:
                ValueError: If the function is already registered.
            """
            name = func.__qualname__
            logger.info("registering function '%s'", name)
            wrapped_func = dispatch.function.Function(self._endpoint, name, func)
            if name in self._functions:
                raise ValueError(f"Function {name} already registered")
            self._functions[name] = wrapped_func
            return wrapped_func

        return wrap

    def call(
        self, fn: FunctionType | dispatch.function.Function | str, input: Any = None
    ) -> DispatchID:
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

        if isinstance(fn, FunctionType):
            fn = fn.__name__
        elif isinstance(fn, dispatch.function.Function):
            fn = fn.name

        try:
            wrapped_func = self._functions[fn]
        except KeyError:
            raise ValueError(
                f"function {fn} has not been registered (via @dispatch.function)"
            )

        [dispatch_id] = self._client.dispatch([wrapped_func.call_with(input)])
        return dispatch_id
