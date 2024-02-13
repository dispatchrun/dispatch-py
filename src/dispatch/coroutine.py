import enum
from dataclasses import dataclass
from typing import Any

from dispatch.experimental.durable.function import DurableGenerator
from dispatch.experimental.multicolor import yields
from dispatch.proto import Call, CallResult


class Directive(enum.Enum):
    """Directives instruct the Dispatch orchestrator."""

    EXIT = 0
    POLL = 1


@yields(type=Directive.EXIT)
def exit(result: Any = None, tail_call: Call | None = None):
    raise InvalidContextError


@yields(type=Directive.POLL)
def poll(calls: list[Call] | None = None) -> list[CallResult]:
    raise InvalidContextError


class InvalidContextError(RuntimeError):
    """A directive was used outside a @dispatch.coroutine."""


@dataclass
class CoroutineState:
    generator: DurableGenerator
    version: str
