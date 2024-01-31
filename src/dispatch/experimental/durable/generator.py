from types import GeneratorType, TracebackType, CodeType, FrameType
from typing import Generator, TypeVar
from .registry import lookup_function
from . import frame as ext


_YieldT = TypeVar("_YieldT", covariant=True)
_SendT = TypeVar("_SendT", contravariant=True)
_ReturnT = TypeVar("_ReturnT", covariant=True)


class DurableGenerator(Generator[_YieldT, _SendT, _ReturnT]):
    """A generator that can be pickled."""

    def __init__(self, gen: GeneratorType, key, args, kwargs):
        self.generator = gen

        # Capture the information necessary to be able to create a
        # new instance of the generator.
        self.key = key
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
        frame = self.generator.gi_frame
        state = {
            "function": {
                "key": self.key,
                "args": self.args,
                "kwargs": self.kwargs,
            },
            "generator": {
                "frame_state": ext.get_generator_frame_state(self.generator),
            },
            "frame": {
                "ip": ext.get_frame_ip(frame),  # aka. frame.f_lasti
                "sp": ext.get_frame_sp(frame),
                "stack": [
                    ext.get_frame_stack_at(frame, i)
                    for i in range(ext.get_frame_sp(frame))
                ],
            },
        }
        return state

    def __setstate__(self, state):
        function_state = state["function"]
        generator_state = state["generator"]
        frame_state = state["frame"]

        # Recreate the generator by looking up the constructor
        # and calling it with the same args/kwargs.
        self.key, self.args, self.kwargs = (
            function_state["key"],
            function_state["args"],
            function_state["kwargs"],
        )
        generator_fn = lookup_function(self.key)
        self.generator = generator_fn(*self.args, **self.kwargs)

        # Restore the frame state (stack + stack pointer + instruction pointer).
        frame = self.generator.gi_frame
        ext.set_frame_ip(frame, frame_state["ip"])
        ext.set_frame_sp(frame, frame_state["sp"])
        for i, (is_null, obj) in enumerate(frame_state["stack"]):
            ext.set_frame_stack_at(frame, i, is_null, obj)

        # Restore the generator state (the frame state field tracks whether the
        # frame is newly created, or whether it was previously suspended).
        ext.set_generator_frame_state(self.generator, generator_state["frame_state"])
