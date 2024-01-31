from types import FunctionType


_REGISTRY: dict[str, FunctionType] = {}


def register_function(fn: FunctionType) -> str:
    # We need to be able to refer to the function in the serialized
    # representation, and the key needs to be stable across interpreter
    # invocations. Use the code object's fully-qualified name for now.
    # If there are name clashes, the location of the function
    # (co_filename + co_firstlineno) and/or a hash of the bytecode
    # (co_code) could be used as well or instead.
    key = fn.__code__.co_qualname
    if key in _REGISTRY:
        raise ValueError(f"durable function already registered with key {key}")

    _REGISTRY[key] = fn

    return key


def lookup_function(key: str) -> FunctionType:
    return _REGISTRY[key]
