import ast
import inspect
import textwrap
from types import FunctionType
from typing import cast


def parse_function(fn: FunctionType) -> tuple[ast.Module, ast.FunctionDef]:
    """Parse an AST from a function. The function source must be available.

    Args:
        fn: The function to parse.

    Raises:
        NoSourceError: If the function source cannot be retrieved.
    """
    try:
        src = inspect.getsource(fn)
    except TypeError as e:
        # The source is not always available. For example, the function
        # may be defined in a C extension, or may be a builtin function.
        raise NoSourceError from e
    except OSError as e:
        raise NoSourceError from e

    try:
        module = ast.parse(src)
    except IndentationError:
        module = ast.parse(textwrap.dedent(src))

    fn_def = cast(ast.FunctionDef, module.body[0])
    return module, fn_def


class NoSourceError(RuntimeError):
    """Function source code is not available."""
