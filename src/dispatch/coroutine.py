"""Dispatch coroutine interface.
"""

from typing import Any
from dataclasses import dataclass
import pickle


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

    def __init__(self, input: None | bytes, poll_response: None | Any):
        # _has_input is used to tracked whether some bytes were provided, to
        # differentiate with a pickled None.
        self._has_input = input is not None
        if input is not None:
            self._input = pickle.loads(input) if len(input) > 0 else None

    @property
    def is_first_call(self) -> bool:
        return self._has_input

    @property
    def is_resume(self) -> bool:
        return not self.is_first_call

    @property
    def input(self) -> Any:
        if not self._has_input:
            raise ValueError("This input is for a resumed coroutine")
        return self._input
