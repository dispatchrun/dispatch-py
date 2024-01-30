"""Dispatch coroutine interface.

Coroutines are currently created using the @app.dispatch_coroutine() decorator
in a FastAPI app. See dispatch.fastapi for more details and examples. This
module describes how to write functions that get turned into coroutines.

Coroutines are functions that can yield at any point in their execution to save
progress and coordinate with other coroutines. They take exactly one argument of
type Input, and return an Output value.

"""

from __future__ import annotations
from typing import Any
from dataclasses import dataclass
import google.protobuf.message
import pickle
from ring.coroutine.v1 import coroutine_pb2


class Input:
    """The input to a coroutine.

    Coroutines always take a single argument of type Input. If the coroutine is
    started, it contains the input to the coroutine. If the coroutine is
    resumed, it contains the saved state and response to any poll requests. Use
    the is_first_call and is_resume properties to differentiate between the two
    cases.

    This class is intended to be used as read-only.

    """

    # TODO: first implementation with a single Input type, but we should
    # consider using some dynamic filling positional and keyword arguments.

    def __init__(self, req: coroutine_pb2.ExecuteRequest):
        self._has_input = req.HasField("input")
        if self._has_input:
            input_pb = google.protobuf.wrappers_pb2.BytesValue()
            req.input.Unpack(input_pb)
            input_bytes = input_pb.value
            if len(input_bytes) > 0:
                self._input = pickle.loads(input_bytes)
            else:
                self._input = None
        else:
            state_bytes = req.poll_response.state
            if len(state_bytes) > 0:
                self._state = pickle.loads(state_bytes)
            else:
                self._state = None

    @property
    def is_first_call(self) -> bool:
        return self._has_input

    @property
    def is_resume(self) -> bool:
        return not self.is_first_call

    @property
    def input(self) -> Any:
        if self.is_resume:
            raise ValueError("This input is for a resumed coroutine")
        return self._input

    @property
    def state(self) -> Any:
        if self.is_first_call:
            raise ValueError("This input is for a first coroutine call")
        return self._state


class Output:
    """The output of a coroutine.

    This class is meant to be instantiated and returned by authors of coroutines
    to indicate the follow up action they need to take.
    """

    def __init__(self, proto: coroutine_pb2.ExecuteResponse):
        self._message = proto

    @classmethod
    def value(cls, value: Any) -> Output:
        """Terminally exit the coroutine with the provided return value."""
        output_any = _pb_any_pickle(value)
        return Output(
            coroutine_pb2.ExecuteResponse(
                exit=coroutine_pb2.Exit(result=coroutine_pb2.Result(output=output_any))
            )
        )

    @classmethod
    def callback(cls, state: Any) -> Output:
        """Exit the coroutine instructing the orchestrator to call back this
        coroutine with the provided state. The state will be made available in
        Input.state."""
        state_bytes = pickle.dumps(state)
        return Output(
            coroutine_pb2.ExecuteResponse(poll=coroutine_pb2.Poll(state=state_bytes))
        )


def _pb_any_pickle(x: Any) -> google.protobuf.any_pb2.Any:
    value_bytes = pickle.dumps(x)
    pb_bytes = google.protobuf.wrappers_pb2.BytesValue(value=value_bytes)
    pb_any = google.protobuf.any_pb2.Any()
    pb_any.Pack(pb_bytes)
    return pb_any
