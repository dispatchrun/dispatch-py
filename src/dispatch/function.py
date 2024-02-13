from __future__ import annotations

import functools
import inspect
import logging
import pickle
import sys
from types import FunctionType
from typing import Any, Callable, Dict, TypeAlias

from dispatch.client import Client
from dispatch.coroutine import CoroutineState, Directive
from dispatch.experimental.durable import durable
from dispatch.experimental.multicolor import (
    CustomYield,
    GeneratorYield,
    compile_function,
    no_yields,
)
from dispatch.id import DispatchID
from dispatch.proto import Call, CallResult, Error, Input, Output, _Arguments
from dispatch.status import Status, status_for_output

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

    @no_yields
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
        return self._register_function

    def coroutine(self) -> Callable[[FunctionType], Function | FunctionType]:
        """Returns a decorator that registers coroutine functions."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._register_coroutine

    def primitive_function(self) -> Callable[[PrimitiveFunctionType], Function]:
        """Returns a decorator that registers primitive functions."""

        # Note: the indirection here means that we can add parameters
        # to the decorator later without breaking existing apps.
        return self._register_primitive_function

    def _register_function(self, func: FunctionType) -> Function:
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
                try:
                    args, kwargs = input.input_arguments()
                except ValueError:
                    raise ValueError("incorrect input for function")
                raw_output = func(*args, **kwargs)
            except Exception as e:
                return Output.error(Error.from_exception(e))
            else:
                return Output.value(raw_output)

        return self._register_primitive_function(primitive_func)

    def _register_coroutine(self, func: FunctionType) -> Function | FunctionType:
        """(EXPERIMENTAL) Register a coroutine function with the Dispatch
        programmable endpoints.

        The function is compiled into a durable coroutine.

        The coroutine can use directives such as poll() partway through
        execution. The coroutine will be suspended at these yield points,
        and will resume execution from the same point when results are
        available. The state of the coroutine is stored durably across
        yield points.

        Args:
            func: The coroutine to register.

        Returns:
            Function: A registered Dispatch Function.

        Raises:
            ValueError: If the function is already registered.
        """

        # FIXME: this is a funny issue that occurs where the compiled function
        #  below has the same decorator and is thus registered again
        for frame_info in inspect.stack():
            if frame_info.function == compile_function.__name__:
                return func

        compiled_func = compile_function(func, decorator=durable, cache_key="dispatch")

        @functools.wraps(func)
        def primitive_coro_func(input: Input) -> Output:
            try:
                # (Re)hydrate the coroutine.
                if input.is_first_call:
                    logger.debug("starting coroutine")
                    try:
                        args, kwargs = input.input_arguments()
                    except ValueError:
                        raise ValueError("incorrect input for function")

                    gen = compiled_func(*args, **kwargs)
                    send = None
                else:
                    logger.debug(
                        "resuming coroutine with %d bytes of state and %d call result(s)",
                        len(input.coroutine_state),
                        len(input.call_results),
                    )
                    try:
                        coroutine_state = pickle.loads(input.coroutine_state)
                        if not isinstance(coroutine_state, CoroutineState):
                            raise ValueError("invalid coroutine state")
                        if coroutine_state.version != sys.version:
                            raise ValueError(
                                f"coroutine state version mismatch: '{coroutine_state.version}' vs. current '{sys.version}'"
                            )
                    except (pickle.PickleError, ValueError) as e:
                        logger.warning("coroutine state is incompatible", exc_info=True)
                        return Output.error(
                            Error.from_exception(e, status=Status.INCOMPATIBLE_STATE)
                        )
                    gen = coroutine_state.generator
                    send = input.call_results

                # Run the coroutine until its next yield or return.
                try:
                    directive = gen.send(send)
                except StopIteration as e:
                    logger.debug("coroutine returned")
                    return Output.value(e.value)  # Return value.

                # Handle directives that it yields.
                logger.debug("handling coroutine directive: %s", directive)
                match directive:
                    case CustomYield(type=Directive.EXIT):
                        result = directive.kwarg("result", 0)
                        tail_call = directive.kwarg("tail_call", 1)
                        status = status_for_output(result)
                        return Output.exit(
                            result=CallResult.from_value(result),
                            tail_call=tail_call,
                            status=status,
                        )

                    case CustomYield(type=Directive.POLL):
                        try:
                            coroutine_state = pickle.dumps(
                                CoroutineState(generator=gen, version=sys.version)
                            )
                        except pickle.PickleError as e:
                            logger.error(
                                "coroutine could not be serialized", exc_info=True
                            )
                            return Output.error(
                                Error.from_exception(e, status=Status.PERMANENT_ERROR)
                            )
                        calls = directive.kwarg("calls", 0)
                        return Output.poll(state=coroutine_state, calls=calls)

                    case _:
                        if isinstance(directive, GeneratorYield):
                            directive = directive.value
                        raise RuntimeError(
                            f"coroutine unexpectedly yielded '{directive}'"
                        )

            except Exception as e:
                logger.error("coroutine raised exception", exc_info=True)
                return Output.error(Error.from_exception(e))

        return self._register_primitive_function(primitive_coro_func)

    def _register_primitive_function(self, func: PrimitiveFunctionType) -> Function:
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
