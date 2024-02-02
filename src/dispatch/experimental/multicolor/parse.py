import ast
import inspect
from types import FunctionType
from typing import cast


def parse_function(fn: FunctionType) -> tuple[ast.Module, ast.FunctionDef]:
    """Parse an AST from a function definition."""
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
        src = repair_indentation(src)
        module = ast.parse(src)

    fn_def = cast(ast.FunctionDef, module.body[0])
    return module, fn_def


class NoSourceError(RuntimeError):
    """Error that occurs when a function AST is not available because
    the (Python) source code is not available."""


def repair_indentation(src: str) -> str:
    """Repair (remove excess) indentation from the source of a function
    definition that's nested within a class or function."""
    lines = src.split("\n")
    head = lines[0]
    indent_len = len(head) - len(head.lstrip())
    indent = head[:indent_len]
    for i in range(len(lines)):
        if len(lines[i]) == 0:
            continue
        if not lines[i].startswith(indent):
            raise IndentationError(
                f"inconsistent indentation '{head}' vs. '{lines[i]}'"
            )
        lines[i] = lines[i][indent_len:]
    return "\n".join(lines)
