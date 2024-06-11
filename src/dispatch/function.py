from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import threading
from functools import wraps
from types import CoroutineType
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
from dispatch.scheduler import OneShotScheduler

logger = logging.getLogger(__name__)


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


class ThreadContext(threading.local):
    in_function_call: bool

    def __init__(self):
        self.in_function_call = False


thread_context = ThreadContext()


def function(func: Callable[P, T]) -> Callable[P, T]:
    def scope(*args: P.args, **kwargs: P.kwargs) -> T:
        if thread_context.in_function_call:
            raise RuntimeError("recursively entered a dispatch function entry point")
        thread_context.in_function_call = True
        try:
            return func(*args, **kwargs)
        finally:
            thread_context.in_function_call = False

    return scope


PrimitiveFunctionType: TypeAlias = Callable[[Input], Awaitable[Output]]
"""A primitive function is a function that accepts a dispatch.proto.Input
and unconditionally returns a dispatch.proto.Output. It must not raise
exceptions.
"""


class PrimitiveFunction:
    __slots__ = ("_endpoint", "_client", "_name", "_primitive_func")
    _endpoint: str
    _client: Client
    _name: str
    _primitive_function: PrimitiveFunctionType

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

    @endpoint.setter
    def endpoint(self, value: str):
        self._endpoint = value

    @property
    def name(self) -> str:
        return self._name

    async def _primitive_call(self, input: Input) -> Output:
        return await self._primitive_func(input)

    async def _primitive_dispatch(self, input: Any = None) -> DispatchID:
        [dispatch_id] = await self._client.dispatch([self._build_primitive_call(input)])
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
    ):
        PrimitiveFunction.__init__(self, endpoint, client, name, primitive_func)
        self._func_indirect: Callable[P, Coroutine[Any, Any, T]] = durable(
            self._call_async
        )

    async def _call_async(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return await dispatch.coroutine.call(self.build_call(*args, **kwargs))

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        """Call the function asynchronously (through Dispatch), and return a
        coroutine that can be awaited to retrieve the call result."""
        if thread_context.in_function_call:
            return await self._func_indirect(*args, **kwargs)

        call = self.build_call(*args, **kwargs)

        [dispatch_id] = await self._client.dispatch([call])

        return await self._client.wait(dispatch_id)

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
        """
        return asyncio.run(self._primitive_dispatch(Arguments(args, kwargs)))

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


class Reset(TailCall):
    """The current coroutine is aborted and scheduling reset to be replaced with
    the call embedded in this exception."""

    def __init__(self, func: Function[P, T], *args: P.args, **kwargs: P.kwargs):
        super().__init__(call=func.build_call(*args, **kwargs))


class Registry:
    """Registry of functions."""

    __slots__ = ("functions", "endpoint", "client")

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """Initialize a function registry.

        Args:
            endpoint: URL of the endpoint that the function is accessible from.
                Uses the value of the DISPATCH_ENDPOINT_URL environment variable
                by default.

            api_key: Dispatch API key to use for authentication when
                dispatching calls to functions. Uses the value of the
                DISPATCH_API_KEY environment variable by default.

            api_url: The URL of the Dispatch API to use when dispatching calls
                to functions. Uses the value of the DISPATCH_API_URL environment
                variable if set, otherwise defaults to the public Dispatch API
                (DEFAULT_API_URL).

        Raises:
            ValueError: If any of the required arguments are missing.
        """
        endpoint_from = "endpoint argument"
        if not endpoint:
            endpoint = os.getenv("DISPATCH_ENDPOINT_URL")
            endpoint_from = "DISPATCH_ENDPOINT_URL"
        if not endpoint:
            raise ValueError(
                "missing application endpoint: set it with the DISPATCH_ENDPOINT_URL environment variable"
            )
        parsed_url = urlparse(endpoint)
        if not parsed_url.netloc or not parsed_url.scheme:
            raise ValueError(
                f"{endpoint_from} must be a full URL with protocol and domain (e.g., https://example.com)"
            )
        logger.info("configuring Dispatch endpoint %s", endpoint)
        self.functions: Dict[str, PrimitiveFunction] = {}
        self.endpoint = endpoint
        self.client = Client(api_key=api_key, api_url=api_url)

    @overload
    def function(self, func: Callable[P, Coroutine[Any, Any, T]]) -> Function[P, T]: ...

    @overload
    def function(self, func: Callable[P, T]) -> Function[P, T]: ...

    def function(self, func):
        """Decorator that registers functions."""
        name = func.__qualname__

        if not inspect.iscoroutinefunction(func):
            logger.info("registering function: %s", name)
            return self._register_function(name, func)

        logger.info("registering coroutine: %s", name)
        return self._register_coroutine(name, func)

    def _register_function(self, name: str, func: Callable[P, T]) -> Function[P, T]:
        func = durable(func)

        @wraps(func)
        @function
        async def asyncio_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, func, *args, **kwargs)

        asyncio_wrapper.__qualname__ = f"{name}_asyncio"
        return self._register_coroutine(name, asyncio_wrapper)

    def _register_coroutine(
        self, name: str, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Function[P, T]:
        logger.info("registering coroutine: %s", name)
        func = durable(func)

        @wraps(func)
        @function
        async def primitive_func(input: Input) -> Output:
            return await OneShotScheduler(func).run(input)

        primitive_func.__qualname__ = f"{name}_primitive"
        durable_primitive_func = durable(primitive_func)

        wrapped_func = Function[P, T](
            self.endpoint,
            self.client,
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
        wrapped_func = PrimitiveFunction(
            self.endpoint,
            self.client,
            name,
            primitive_func,
        )
        self._register(name, wrapped_func)
        return wrapped_func

    def _register(self, name: str, wrapped_func: PrimitiveFunction):
        if name in self.functions:
            raise ValueError(f"function already registered with name '{name}'")
        self.functions[name] = wrapped_func

    def batch(self):  # -> Batch:
        """Returns a Batch instance that can be used to build
        a set of calls to dispatch."""
        # return self.client.batch()
        raise NotImplemented

    def set_client(self, client: Client):
        """Set the Client instance used to dispatch calls to registered functions."""
        # TODO: figure out a way to remove this method, it's only used in examples
        self.client = client
        for fn in self.functions.values():
            fn._client = client

    def override_endpoint(self, endpoint: str):
        for fn in self.functions.values():
            fn.endpoint = endpoint


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

        dispatch_ids = [DispatchID(x) for x in resp.dispatch_ids]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "dispatched %d function call(s): %s",
                len(calls_proto),
                ", ".join(dispatch_ids),
            )
        return dispatch_ids

    async def wait(self, dispatch_id: DispatchID) -> Any:
        (url, headers, timeout) = self.request("/dispatch.sdk.v1.DispatchService/Wait")
        data = dispatch_id.encode("utf-8")

        async with self.session() as session:
            async with session.post(
                url, headers=headers, data=data, timeout=timeout
            ) as res:
                data = await res.read()
                self._check_response(res.status, data)

        resp = call_pb.CallResult()
        resp.ParseFromString(data)

        result = CallResult._from_proto(resp)
        if result.error is not None:
            raise result.error.to_exception()
        return result.output

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

    def add(self, func: Function[P, T], *args: P.args, **kwargs: P.kwargs) -> Batch:
        """Add a call to the specified function to the batch."""
        return self.add_call(func.build_call(*args, **kwargs))

    def add_call(self, call: Call) -> Batch:
        """Add a Call to the batch."""
        self.calls.append(call)
        return self

    def dispatch(self) -> List[DispatchID]:
        """Dispatch dispatches the calls asynchronously.

        The batch is reset when the calls are dispatched successfully.

        Returns:
            Identifiers for the function calls, in the same order they
            were added.
        """
        if not self.calls:
            return []
        dispatch_ids = asyncio.run(self.client.dispatch(self.calls))
        self.clear()
        return dispatch_ids

    def clear(self):
        """Reset the batch."""
        self.calls = []
