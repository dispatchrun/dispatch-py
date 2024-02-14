import hashlib
from dataclasses import dataclass
from types import FunctionType


@dataclass
class RegisteredFunction:
    """A function that can be referenced in durable state."""

    key: str
    fn: FunctionType
    filename: str
    lineno: int
    hash: str


_REGISTRY: dict[str, RegisteredFunction] = {}


def register_function(fn: FunctionType) -> RegisteredFunction:
    """Register a function in the in-memory function registry.

    When serializing a registered function, a reference to the function
    is stored along with details about its location and contents. When
    deserializing the function, the registry is consulted in order to
    find the function associated with the reference (and in order to
    check whether the function is the same).

    Args:
        fn: The function to register.

    Returns:
        str: Unique identifier for the function.

    Raises:
        ValueError: The function conflicts with another registered function.
    """
    code = fn.__code__
    rfn = RegisteredFunction(
        key=code.co_qualname,
        fn=fn,
        filename=code.co_filename,
        lineno=code.co_firstlineno,
        hash="sha256:" + hashlib.sha256(code.co_code).hexdigest(),
    )

    try:
        existing = _REGISTRY[rfn.key]
    except KeyError:
        pass
    else:
        if existing == rfn:
            return existing
        raise ValueError(f"durable function already registered with key {rfn.key}")

    _REGISTRY[rfn.key] = rfn
    return rfn


def lookup_function(key: str) -> RegisteredFunction:
    """Lookup a registered function by key.

    Args:
        key: Unique identifier for the function.

    Returns:
        RegisteredFunction: the function that was registered with the specified key.

    Raises:
        KeyError: A function has not been registered with this key.
    """
    return _REGISTRY[key]
