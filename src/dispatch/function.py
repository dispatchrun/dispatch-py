from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)
from urllib.parse import urlparse

import aiohttp
from typing_extensions import ParamSpec, TypeAlias

import dispatch.coroutine
import dispatch.sdk.v1.call_pb2 as call_pb
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
from dispatch.config import NamedValueFromEnvironment
from dispatch.experimental.durable import durable
from dispatch.id import DispatchID
from dispatch.proto import Arguments, Call, CallResult, Error, Input, Output, TailCall
from dispatch.scheduler import OneShotScheduler, in_function_call

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class GlobalSession(aiohttp.ClientSession):
    async def __aexit__(self, *args):
        pass  # don't close global sessions when used as context managers


DEFAULT_API_URL: str = "https://api.dispatch.run"
DEFAULT_SESSION: Optional[aiohttp.ClientSession] = None


def current_session() -> aiohttp.ClientSession:
    global DEFAULT_SESSION
    if DEFAULT_SESSION is None:
        DEFAULT_SESSION = GlobalSession()
    return DEFAULT_SESSION


PrimitiveFunctionType: TypeAlias = Callable[[Input], Awaitable[Output]]
"""A primitive function is a function that accepts a dispatch.proto.Input
and unconditionally returns a dispatch.proto.Output. It must not raise
exceptions.
"""


class PrimitiveFunction:
    __slots__ = ("_registry", "_name", "_primitive_func")
    _registry: str
    _name: str
    _primitive_function: PrimitiveFunctionType

    def __init__(
        self,
        registry: Registry,
        name: str,
        primitive_func: PrimitiveFunctionType,
    ):
        self._registry = registry.name
        self._name = name
        self._primitive_func = primitive_func

    @property
    def endpoint(self) -> str:
        return self.registry.endpoint

    @property
    def name(self) -> str:
        return self._name

    @property
    def registry(self) -> Registry:
        return lookup_registry(self._registry)

    async def _primitive_call(self, input: Input) -> Output:
        return await self._primitive_func(input)

    async def _primitive_dispatch(self, input: Any = None) -> DispatchID:
        [dispatch_id] = await self.registry.client.dispatch(
            [self._build_primitive_call(input)]
        )
        return dispatch_id

    def _build_primitive_call(
        self, input: Any, correlation_id: Optional[int] = None
    ) -> Call:
        return Call(
            correlation_id=correlation_id,
            endpoint=self.endpoint,
            function=self.name,
            input=input,
        )


class AsyncFunction(PrimitiveFunction, Generic[P, T]):
    """Callable wrapper around a function meant to be used throughout the
    Dispatch Python SDK.
    """

    __slots__ = ("_func_indirect",)

    def __init__(
        self,
        registry: Registry,
        name: str,
        primitive_func: PrimitiveFunctionType,
    ):
        PrimitiveFunction.__init__(self, registry, name, primitive_func)
        self._func_indirect: Callable[P, Coroutine[Any, Any, T]] = durable(
            self._call_async
        )

    async def _call_async(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return await dispatch.coroutine.call(self.build_call(*args, **kwargs))

    async def _call_dispatch(self, *args: P.args, **kwargs: P.kwargs) -> T:
        call = self.build_call(*args, **kwargs)
        client = self.registry.client
        [dispatch_id] = await client.dispatch([call])
        return await client.wait(dispatch_id)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, T]:
        """Call the function asynchronously (through Dispatch), and return a
        coroutine that can be awaited to retrieve the call result."""
        # Note: this method cannot be made `async`, otherwise Python creates
        # ont additional wrapping layer of native coroutine that cannot be
        # pickled and breaks serialization.
        #
        # The durable coroutine returned by calling _func_indirect must be
        # returned as is.
        #
        # For cases where this method is called outside the context of a
        # dispatch function, it still returns a native coroutine object,
        # but that doesn't matter since there is no state serialization in
        # that case.
        if in_function_call():
            return self._func_indirect(*args, **kwargs)
        else:
            return self._call_dispatch(*args, **kwargs)

    async def dispatch(self, *args: P.args, **kwargs: P.kwargs) -> DispatchID:
        """Dispatch an asynchronous call to the function without
        waiting for a result.

        The Registry this function was registered with must be initialized
        with a Client / api_key for this call facility to be available.

        Args:
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            DispatchID: ID of the dispatched call.
        """
        return await self._primitive_dispatch(Arguments(args, kwargs))

    def build_call(self, *args: P.args, **kwargs: P.kwargs) -> Call:
        """Create a Call for this function with the provided input. Useful to
        generate calls when using the Client.

        Args:
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Call: can be passed to Client.dispatch.
        """
        return self._build_primitive_call(Arguments(args, kwargs))


class BlockingFunction(Generic[P, T]):
    """BlockingFunction is like Function but exposes a blocking API instead of
    functions that use asyncio.

    Applications typically don't create instances of BlockingFunction directly,
    and instead use decorators from packages that provide integrations with
    Python frameworks.
    """

    def __init__(self, func: AsyncFunction[P, T]):
        self._func = func

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(self._func(*args, **kwargs))

    def dispatch(self, *args: P.args, **kwargs: P.kwargs) -> DispatchID:
        return asyncio.run(self._func.dispatch(*args, **kwargs))

    def build_call(self, *args: P.args, **kwargs: P.kwargs) -> Call:
        return self._func.build_call(*args, **kwargs)


class Reset(TailCall):
    """The current coroutine is aborted and scheduling reset to be replaced with
    the call embedded in this exception."""

    def __init__(
        self,
        func: Union[AsyncFunction[P, T], BlockingFunction[P, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        super().__init__(call=func.build_call(*args, **kwargs))


class Registry:
    """Registry of functions."""

    __slots__ = ("functions", "client", "_name", "_endpoint")

    def __init__(
        self, name: str, client: Optional[Client] = None, endpoint: Optional[str] = None
    ):
        """Initialize a function registry.

        Args:
            name: A unique name for the registry.

            endpoint: URL of the endpoint that the function is accessible from.

            client: Client instance to use for dispatching calls to registered
                functions. Defaults to creating a new client instance.

        Raises:
            ValueError: If any of the required arguments are missing.
        """
        if not endpoint:
            endpoint = os.getenv("DISPATCH_ENDPOINT_URL")
        if not endpoint:
            raise ValueError(
                "missing application endpoint: set it with the DISPATCH_ENDPOINT_URL environment variable"
            )
        logger.info("configuring Dispatch endpoint %s", endpoint)
        self.functions: Dict[str, PrimitiveFunction] = {}
        self.client = client or Client()
        self.endpoint = endpoint

        if not name:
            raise ValueError("missing registry name")
        if name in _registries:
            raise ValueError(f"registry with name '{name}' already exists")
        self._name = name
        _registries[name] = self

    def close(self):
        """Closes the registry, removing it and all its functions from the
        dispatch application."""
        name = self._name
        if name:
            self._name = ""
            del _registries[name]
            # TODO: remove registered functions

    @property
    def name(self) -> str:
        return self._name

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str):
        parsed = urlparse(value)
        if not parsed.scheme:
            raise ValueError(
                f"missing protocol scheme in registry endpoint URL: {value}"
            )
        if parsed.scheme not in ("bridge", "http", "https"):
            raise ValueError(
                f"invalid protocol scheme in registry endpoint URL: {value}"
            )
        if not parsed.hostname:
            raise ValueError(f"missing host in registry endpoint URL: {value}")
        self._endpoint = value

    @overload
    def function(
        self, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> AsyncFunction[P, T]: ...

    @overload
    def function(self, func: Callable[P, T]) -> AsyncFunction[P, T]: ...

    def function(self, func):
        """Decorator that registers functions."""
        name = func.__qualname__

        if not inspect.iscoroutinefunction(func):
            logger.info("registering function: %s", name)
            return self._register_function(name, func)

        logger.info("registering coroutine: %s", name)
        return self._register_coroutine(name, func)

    def _register_function(
        self, name: str, func: Callable[P, T]
    ) -> AsyncFunction[P, T]:
        func = durable(func)

        @wraps(func)
        async def asyncio_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)

        asyncio_wrapper.__qualname__ = f"{name}_asyncio"
        return self._register_coroutine(name, asyncio_wrapper)

    def _register_coroutine(
        self, name: str, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> AsyncFunction[P, T]:
        logger.info("registering coroutine: %s", name)
        func = durable(func)

        @wraps(func)
        async def primitive_func(input: Input) -> Output:
            return await OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{name}_primitive"
        durable_primitive_func = durable(primitive_func)

        wrapped_func = AsyncFunction[P, T](
            self,
            name,
            durable_primitive_func,
        )
        self._register(name, wrapped_func)
        return wrapped_func

    def primitive_function(
        self, primitive_func: PrimitiveFunctionType
    ) -> PrimitiveFunction:
        """Decorator that registers primitive functions."""
        name = primitive_func.__qualname__
        logger.info("registering primitive function: %s", name)
        wrapped_func = PrimitiveFunction(self, name, primitive_func)
        self._register(name, wrapped_func)
        return wrapped_func

    def _register(self, name: str, wrapped_func: PrimitiveFunction):
        if name in self.functions:
            raise ValueError(f"function already registered with name '{name}'")
        self.functions[name] = wrapped_func

    def batch(self) -> Batch:
        """Returns a Batch instance that can be used to build
        a set of calls to dispatch."""
        return Batch(self.client)


_registries: Dict[str, Registry] = {}

DEFAULT_REGISTRY_NAME: str = "default"
DEFAULT_REGISTRY: Optional[Registry] = None
"""The default registry for dispatch functions, used by dispatch applications
when no custom registry is provided.

In most cases, applications do not need to create a custom registry, so this
one would be used by default.

The default registry use DISPATCH_* environment variables for configuration,
or is uninitialized if they are not set.
"""


def default_registry() -> Registry:
    """Returns the default registry for dispatch functions.

    The function initializes the default registry if it has not been initialized
    yet, using the DISPATCH_* environment variables for configuration.

    Returns:
        Registry: The default registry.

    Raises:
        ValueError: If the DISPATCH_API_KEY or DISPATCH_ENDPOINT_URL environment
            variables are missing.
    """
    global DEFAULT_REGISTRY
    if DEFAULT_REGISTRY is None:
        DEFAULT_REGISTRY = Registry(DEFAULT_REGISTRY_NAME)
    return DEFAULT_REGISTRY


def lookup_registry(name: str) -> Registry:
    return default_registry() if name == DEFAULT_REGISTRY_NAME else _registries[name]


def set_default_registry(reg: Registry):
    global DEFAULT_REGISTRY
    global DEFAULT_REGISTRY_NAME
    DEFAULT_REGISTRY = reg
    DEFAULT_REGISTRY_NAME = reg.name


# TODO: this is a temporary solution to track inflight tasks and allow waiting
# for results.
_calls: Dict[str, asyncio.Future] = {}


class Client:
    """Client for the Dispatch API."""

    __slots__ = ("api_url", "api_key")

    api_url: NamedValueFromEnvironment
    api_key: NamedValueFromEnvironment

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
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
        self.api_url = NamedValueFromEnvironment("DISPATCH_API_URL", "api_url", api_url)
        self.api_key = NamedValueFromEnvironment("DISPATCH_API_KEY", "api_key", api_key)

        if not self.api_key.value:
            raise ValueError(
                "missing API key: set it with the DISPATCH_API_KEY environment variable"
            )

        if not self.api_url.value:
            if "DISPATCH_API_URL" in os.environ:
                raise ValueError(
                    "missing API URL: set it with the DISPATCH_API_URL environment variable"
                )
            self.api_url._value = DEFAULT_API_URL

        result = urlparse(self.api_url.value)
        if result.scheme not in ("http", "https"):
            raise ValueError(f"Invalid API scheme: '{result.scheme}'")

        logger.debug(
            "initializing client for Dispatch API at URL %s", self.api_url.value
        )

    def session(self) -> aiohttp.ClientSession:
        return current_session()

    def request(
        self, path: str, timeout: int = 5
    ) -> Tuple[str, dict[str, str], aiohttp.ClientTimeout]:
        # https://connectrpc.com/docs/protocol/#unary-request
        headers = {
            "Authorization": "Bearer " + self.api_key.value,
            "Content-Type": "application/proto",
            "Connect-Protocol-Version": "1",
            "Connect-Timeout-Ms": str(timeout * 1000),
        }
        return self.api_url.value + path, headers, aiohttp.ClientTimeout(total=timeout)

    async def dispatch(self, calls: Iterable[Call]) -> List[DispatchID]:
        """Dispatch function calls.

        Args:
            calls: Calls to dispatch.

        Returns:
            Identifiers for the function calls, in the same order as the inputs.
        """
        calls_proto = [c._as_proto() for c in calls]
        logger.debug("dispatching %d function call(s)", len(calls_proto))
        data = dispatch_pb.DispatchRequest(calls=calls_proto).SerializeToString()

        (url, headers, timeout) = self.request(
            "/dispatch.sdk.v1.DispatchService/Dispatch"
        )

        async with self.session() as session:
            async with session.post(
                url, headers=headers, data=data, timeout=timeout
            ) as res:
                data = await res.read()
                self._check_response(res.status, data)

        resp = dispatch_pb.DispatchResponse()
        resp.ParseFromString(data)

        # TODO: remove when we implemented the wait endpoint in the server
        for dispatch_id in resp.dispatch_ids:
            if dispatch_id not in _calls:
                _calls[dispatch_id] = asyncio.Future()

        dispatch_ids = [DispatchID(x) for x in resp.dispatch_ids]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "dispatched %d function call(s): %s",
                len(calls_proto),
                ", ".join(dispatch_ids),
            )
        return dispatch_ids

    async def wait(self, dispatch_id: DispatchID) -> Any:
        # (url, headers, timeout) = self.request("/dispatch.sdk.v1.DispatchService/Wait")
        # data = dispatch_id.encode("utf-8")

        # async with self.session() as session:
        #     async with session.post(
        #         url, headers=headers, data=data, timeout=timeout
        #     ) as res:
        #         data = await res.read()
        #         self._check_response(res.status, data)

        # resp = call_pb.CallResult()
        # resp.ParseFromString(data)

        # result = CallResult._from_proto(resp)
        # if result.error is not None:
        #     raise result.error.to_exception()
        # return result.output

        future = _calls[dispatch_id]
        return await future

    def _check_response(self, status: int, data: bytes):
        if status == 200:
            return
        if status == 401:
            raise PermissionError(
                f"Dispatch received an invalid authentication token (check {self.api_key.name} is correct)"
            )
        raise ClientError.from_response(status, data)


class ClientError(aiohttp.ClientError):
    status: int
    code: str
    message: str

    def __init__(
        self, status: int = 0, code: str = "unknown", message: str = "unknown"
    ):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    @classmethod
    def from_response(cls, status: int, body: bytes) -> ClientError:
        try:
            error_dict = json.loads(body)
            error_code = str(error_dict.get("code")) or "unknown"
            error_message = str(error_dict.get("message")) or "unknown"
        except json.JSONDecodeError:
            error_code = "unknown"
            error_message = str(body)
        return cls(status, error_code, error_message)


class Batch:
    """A batch of calls to dispatch."""

    __slots__ = ("client", "calls")
    client: Client
    calls: List[Call]

    def __init__(self, client: Client):
        self.client = client
        self.calls = []

    def add(
        self, func: AsyncFunction[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Batch:
        """Add a call to the specified function to the batch."""
        return self.add_call(func.build_call(*args, **kwargs))

    def add_call(self, call: Call) -> Batch:
        """Add a Call to the batch."""
        self.calls.append(call)
        return self

    def clear(self):
        """Reset the batch."""
        self.calls = []

    async def dispatch(self) -> List[DispatchID]:
        """Dispatch dispatches the calls asynchronously.

        The batch is reset when the calls are dispatched successfully.

        Returns:
            Identifiers for the function calls, in the same order they
            were added.
        """
        if not self.calls:
            return []
        dispatch_ids = await self.client.dispatch(self.calls)
        self.clear()
        return dispatch_ids
