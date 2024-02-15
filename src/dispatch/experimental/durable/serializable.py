import os
from types import CoroutineType, GeneratorType
from typing import Any

from . import frame as ext
from .registry import RegisteredFunction, lookup_function

TRACE = os.getenv("DURABLE_TRACE", False)


class Serializable:
    """A wrapper for a generator or coroutine that makes it serializable."""

    g: GeneratorType | CoroutineType
    registered_fn: RegisteredFunction
    coro_await: bool
    args: list[Any]
    kwargs: dict[str, Any]

    def __init__(
        self,
        g: GeneratorType | CoroutineType,
        registered_fn: RegisteredFunction,
        *args: Any,
        coro_await: bool = False,
        **kwargs: Any,
    ):
        self.g = g
        self.registered_fn = registered_fn
        self.coro_await = coro_await
        self.args = list(args)
        self.kwargs = kwargs

        self.__name__ = registered_fn.fn.__name__
        self.__qualname__ = registered_fn.fn.__qualname__

    def __getstate__(self):
        g = self.g
        rfn = self.registered_fn

        # Capture the details necessary to recreate the generator.
        ip = ext.get_frame_ip(g)
        sp = ext.get_frame_sp(g)
        frame_state = ext.get_frame_state(g)
        stack = [ext.get_frame_stack_at(g, i) for i in range(ext.get_frame_sp(g))]

        if TRACE:
            typ = "GENERATOR" if isinstance(g, GeneratorType) else "COROUTINE"
            print(f"\n[DURABLE] {typ} STATE ({rfn.key}):")
            print(f"function = {rfn.fn.__qualname__} ({rfn.filename}:{rfn.lineno})")
            print(f"code hash = {rfn.hash}")
            print(f"args = {self.args}")
            print(f"kwargs = {self.kwargs}")
            print(f"coro await = {self.coro_await}")
            print(f"IP = {ip}")
            print(f"SP = {sp}")
            print(f"frame state = {frame_state}")
            for i, (is_null, value) in enumerate(stack):
                if is_null:
                    print(f"stack[{i}] = NULL")
                else:
                    print(f"stack[{i}] = {value}")
            print()

        state = {
            "function": rfn,
            "instance": {
                "coro_await": self.coro_await,
                "args": self.args,
                "kwargs": self.kwargs,
            },
            "frame": {
                "ip": ip,
                "sp": sp,
                "stack": stack,
                "state": frame_state,
            },
        }
        return state

    def __setstate__(self, state):
        instance_state = state["instance"]
        frame_state = state["frame"]

        # Recreate the generator/coroutine by looking up the constructor
        # and calling it with the same args/kwargs.
        args, kwargs, coro_await = (
            instance_state["args"],
            instance_state["kwargs"],
            instance_state["coro_await"],
        )

        rfn = state["function"]
        g = rfn.fn(*args, **kwargs)

        if coro_await:
            g = g.__await__()

        # Restore the frame state (stack + stack pointer + instruction pointer).
        ext.set_frame_ip(g, frame_state["ip"])
        ext.set_frame_sp(g, frame_state["sp"])
        for i, (is_null, obj) in enumerate(frame_state["stack"]):
            ext.set_frame_stack_at(g, i, is_null, obj)
        ext.set_frame_state(g, frame_state["state"])

        self.g = g
        self.registered_fn = rfn
        self.coro_await = coro_await
        self.args = args
        self.kwargs = kwargs

        self.__name__ = rfn.fn.__name__
        self.__qualname__ = rfn.fn.__qualname__
