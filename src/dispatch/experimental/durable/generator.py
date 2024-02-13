import os
from types import CodeType, FrameType, GeneratorType, TracebackType
from typing import Any, Generator, TypeVar

from . import frame as ext
from .registry import Function, lookup_function

_YieldT = TypeVar("_YieldT", covariant=True)
_SendT = TypeVar("_SendT", contravariant=True)
_ReturnT = TypeVar("_ReturnT", covariant=True)

TRACE = os.getenv("DURABLE_TRACE", False)


class DurableGenerator(Generator[_YieldT, _SendT, _ReturnT]):
    """A wrapper for a generator that makes it serializable (can be pickled).
    Instances behave like the generators they wrap.

    Attributes:
        generator: The wrapped generator.
        key: A unique identifier for the function that created this generator.
        args: Positional arguments to the function that created this generator.
        kwargs: Keyword arguments to the function that created this generator.
    """

    generator: GeneratorType
    key: str
    args: list[Any]
    kwargs: dict[str, Any]

    def __init__(
        self,
        generator: GeneratorType,
        fn: Function,
        args: list[Any],
        kwargs: dict[str, Any],
    ):
        self.generator = generator
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Generator[_YieldT, _SendT, _ReturnT]:
        return self

    def __next__(self) -> _YieldT:
        return next(self.generator)

    def send(self, send: _SendT) -> _YieldT:
        return self.generator.send(send)

    def throw(self, typ, val=None, tb: TracebackType | None = None) -> _YieldT:
        return self.generator.throw(typ, val, tb)

    def close(self) -> None:
        self.generator.close()

    @property
    def gi_running(self) -> bool:
        return self.generator.gi_running

    @property
    def gi_suspended(self) -> bool:
        return self.generator.gi_suspended

    @property
    def gi_code(self) -> CodeType:
        return self.generator.gi_code

    @property
    def gi_frame(self) -> FrameType:
        return self.generator.gi_frame

    @property
    def gi_yieldfrom(self) -> GeneratorType | None:
        return self.generator.gi_yieldfrom

    def __getstate__(self):
        # Capture the details necessary to recreate the generator.
        g = self.generator
        ip = ext.get_frame_ip(g)
        sp = ext.get_frame_sp(g)
        frame_state = ext.get_generator_frame_state(g)
        stack = [ext.get_frame_stack_at(g, i) for i in range(ext.get_frame_sp(g))]

        if TRACE:
            print(f"\n[DURABLE] GENERATOR STATE ({self.fn.key}):")
            print(
                f"function = {self.fn.fn.__qualname__} ({self.fn.filename}:{self.fn.lineno})"
            )
            print(f"code hash = {self.fn.hash}")
            print(f"args = {self.args}")
            print(f"kwargs = {self.kwargs}")
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
            "function": {
                "key": self.fn.key,
                "filename": self.fn.filename,
                "lineno": self.fn.lineno,
                "hash": self.fn.hash,
                "args": self.args,
                "kwargs": self.kwargs,
            },
            "generator": {
                "frame_state": frame_state,
            },
            "frame": {
                "ip": ip,
                "sp": sp,
                "stack": stack,
            },
        }
        return state

    def __setstate__(self, state):
        function_state = state["function"]
        generator_state = state["generator"]
        frame_state = state["frame"]

        # Recreate the generator by looking up the constructor
        # and calling it with the same args/kwargs.
        key, filename, lineno, hash, self.args, self.kwargs = (
            function_state["key"],
            function_state["filename"],
            function_state["lineno"],
            function_state["hash"],
            function_state["args"],
            function_state["kwargs"],
        )
        # First, check the function is the same.
        fn = lookup_function(key)
        if filename != fn.filename or lineno != fn.lineno:
            raise ValueError(
                f"location mismatch for function {key}: {filename}:{lineno} vs. expected {fn.filename}:{fn.lineno}"
            )
        elif hash != fn.hash:
            raise ValueError(
                f"hash mismatch for function {key}: {hash} vs. expected {fn.hash}"
            )

        self.fn = fn
        self.generator = self.fn.fn(*self.args, **self.kwargs)

        # Restore the frame state (stack + stack pointer + instruction pointer).
        frame = self.generator.gi_frame
        ext.set_frame_ip(frame, frame_state["ip"])
        ext.set_frame_sp(frame, frame_state["sp"])
        for i, (is_null, obj) in enumerate(frame_state["stack"]):
            ext.set_frame_stack_at(frame, i, is_null, obj)

        # Restore the generator state (the frame state field tracks whether the
        # frame is newly created, or whether it was previously suspended).
        ext.set_generator_frame_state(self.generator, generator_state["frame_state"])
