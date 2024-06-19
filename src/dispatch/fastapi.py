"""Integration of Dispatch functions with FastAPI.

Example:

    import fastapi
    from dispatch.fastapi import Dispatch

    app = fastapi.FastAPI()
    dispatch = Dispatch(app)

    @dispatch.function
    def my_function():
        return "Hello World!"

    @app.get("/")
    def read_root():
        my_function.dispatch()
"""

from typing import Any, Callable, Coroutine, TypeVar, overload

from typing_extensions import ParamSpec

from dispatch.asyncio.fastapi import Dispatch as AsyncDispatch
from dispatch.function import BlockingFunction

__all__ = ["Dispatch", "AsyncDispatch"]

P = ParamSpec("P")
T = TypeVar("T")


class Dispatch(AsyncDispatch):
    @overload  # type: ignore
    def function(self, func: Callable[P, T]) -> BlockingFunction[P, T]: ...

    @overload  # type: ignore
    def function(
        self, func: Callable[P, Coroutine[Any, Any, T]]
    ) -> BlockingFunction[P, T]: ...

    def function(self, func):
        return BlockingFunction(super().function(func))
