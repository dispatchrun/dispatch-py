import ast
import inspect
import logging
import os
import textwrap
from enum import Enum
from types import FunctionType, GeneratorType, MethodType
from typing import cast

from .desugar import desugar_function
from .generator import empty_generator, is_generator
from .parse import NoSourceError, parse_function
from .template import rewrite_template
from .yields import CustomYield, GeneratorYield

TRACE = os.getenv("MULTICOLOR_TRACE", False)


logger = logging.getLogger(__name__)


def compile_function(
    fn: FunctionType, decorator=None, cache_key: str = "default"
) -> FunctionType | MethodType:
    """Compile a regular function into a generator that yields data passed
    to functions marked with the @multicolor.yields decorator. Decorated yield
    functions can be called from anywhere in the call stack, and functions
    in between do not have to be generators or async functions (coroutines).

    Example:

        @multicolor.yields(type="sleep")
        def sleep(seconds): ...

        def parent():
            sleep(3)  # yield point

        def grandparent():
            parent()

        compiled_grandparent = multicolor.compile_function(grandparent)
        generator = compiled_grandparent()
        for item in generator:
            print(item)  # multicolor.CustomYield(type="sleep", args=[3])

    Two-way data flow works as expected. At a yield point, generator.send(value)
    can be used to send data back to the yield point and to resume execution.
    The data sent back will be the return value of the function decorated with
    @multicolor.yields:

        @multicolor.yields(type="add")
        def add(a: int, b: int) -> int:
            return a + b  # default/synchronous implementation

        def scheduler(generator):
            try:
                send = None
                while True:
                    item = generator.send(send)
                    match item:
                        case multicolor.CustomYield(type="add"):
                            a, b = item.args
                            print(f"adding {a} + {b}")
                            send = a + b
            except StopIteration as e:
                return e.value  # return value

        def adder(a: int, b: int) -> int:
            return add(a, b)

        compiled_adder = multicolor.compile_function(adder)
        generator = compiled_adder(1, 2)
        result = scheduler(generator)
        print(result) # 3

    The @multicolor.yields decorator does not change the implementation of
    the function it decorates. If the function is run without being
    compiled, the default implementation will be used instead:

        print(adder(1, 2))  # 3

    The default implementation could also raise an error, to ensure that
    the function is only ever called from a compiled function.

    Args:
        fn: The function to compile.
        decorator: An optional decorator to apply to the compiled function.
        cache_key: Cache key to use when caching compiled functions.

    Returns:
        FunctionType: A compiled generator function.
    """
    compiled_fn, _ = _compile_internal(fn, decorator, cache_key)
    return compiled_fn


class FunctionColor(Enum):
    """Color (aka. type/flavor) of a function.

    There are four colors of functions in Python:
    * regular (e.g. def fn(): pass)
    * generator (e.g. def fn(): yield)
    * async (e.g. async def fn(): pass)
    * async generator (e.g. async def fn(): yield)

    Only the first two colors are supported at this time.
    """

    REGULAR_FUNCTION = 0
    GENERATOR_FUNCTION = 1


def _compile_internal(
    fn: FunctionType, decorator: FunctionType | None, cache_key: str
) -> tuple[FunctionType | MethodType, FunctionColor]:
    if hasattr(fn, "_multicolor_yield_type"):
        raise ValueError("cannot compile a yield point directly")

    logger.debug("compiling function %s", fn.__name__)

    # Give the function a unique name.
    fn_name = f"{fn.__name__}_{cache_key}"

    # Check if the function has already been compiled.
    cache_holder = fn
    if isinstance(fn, MethodType):
        cache_holder = fn.__self__.__class__
    if hasattr(cache_holder, "_multicolor_cache"):
        try:
            compiled_fn, color = cache_holder._multicolor_cache[fn_name]
        except KeyError:
            pass
        else:
            if isinstance(fn, MethodType):
                return MethodType(compiled_fn, fn.__self__), color
            return compiled_fn, color

    # Parse an abstract syntax tree from the function source.
    try:
        root, fn_def = parse_function(fn)
    except NoSourceError as e:
        try:
            # This can occur when compiling a nested function definition
            # that was created by the desugaring pass.
            if inspect.getsourcefile(fn) == "<dispatch>":
                return fn, FunctionColor.GENERATOR_FUNCTION
        except TypeError:
            raise e
        else:
            raise

    # Determine what type of function we're working with.
    color = FunctionColor.REGULAR_FUNCTION
    if is_generator(fn_def):
        color = FunctionColor.GENERATOR_FUNCTION

    if TRACE:
        print("\n-------------------------------------------------")
        print("[MULTICOLOR] COMPILING:")
        print(textwrap.dedent(inspect.getsource(fn)).rstrip())

    fn_def.name = fn_name

    # De-sugar the AST to simplify subsequent transformations.
    desugar_function(fn_def)

    if TRACE:
        print("\n[MULTICOLOR] DESUGARED:")
        print(ast.unparse(root))

    # Handle generators by wrapping the values they yield.
    generator_transformer = GeneratorTransformer()
    root = generator_transformer.visit(root)

    # Replace explicit function calls with a gadget that resembles yield from.
    call_transformer = CallTransformer()
    root = call_transformer.visit(root)

    # If the function never yields it won't be considered a generator.
    # Patch the function if necessary to yield from an empty generator, which
    # turns it into a generator.
    if not is_generator(fn_def):
        empty = ast.Name(id="_multicolor_empty_generator", ctx=ast.Load())
        g = ast.Call(func=empty, args=[], keywords=[])
        fn_def.body.insert(0, ast.Expr(ast.YieldFrom(value=g)))

    # Patch AST nodes that were inserted without location info.
    ast.fix_missing_locations(root)

    if TRACE:
        print("\n[MULTICOLOR] RESULT:")
        print(ast.unparse(root))

    # Make necessary objects/classes/functions available to the
    # transformed function.
    namespace = fn.__globals__
    namespace["_multicolor_empty_generator"] = empty_generator
    namespace["_multicolor_no_source_error"] = NoSourceError
    namespace["_multicolor_custom_yield"] = CustomYield
    namespace["_multicolor_generator_yield"] = GeneratorYield
    namespace["_multicolor_compile"] = _compile_internal
    namespace["_multicolor_generator_type"] = GeneratorType
    namespace["_multicolor_decorator"] = decorator
    namespace["_multicolor_cache_key"] = cache_key
    namespace["_multicolor_generator_color"] = FunctionColor.GENERATOR_FUNCTION

    # Re-compile.
    code = compile(root, filename="<dispatch>", mode="exec")
    exec(code, namespace)
    compiled_fn = namespace[fn_name]

    # Apply the custom decorator, if applicable.
    if decorator is not None:
        compiled_fn = decorator(compiled_fn)

    # Cache the compiled function.
    if hasattr(cache_holder, "_multicolor_cache"):
        cache = cast(
            dict[str, tuple[FunctionType, FunctionColor]],
            cache_holder._multicolor_cache,
        )
    else:
        cache = {}
        setattr(cache_holder, "_multicolor_cache", cache)
    cache[fn_name] = (compiled_fn, color)

    if isinstance(fn, MethodType):
        return MethodType(compiled_fn, fn.__self__), color

    return compiled_fn, color


class GeneratorTransformer(ast.NodeTransformer):
    """Wrap ast.Yield values in a GeneratorYield container."""

    def visit_Yield(self, node: ast.Yield) -> ast.Yield:
        value = node.value
        if node.value is None:
            value = ast.Constant(value=None)

        wrapped_value = ast.Call(
            func=ast.Name(id="_multicolor_generator_yield", ctx=ast.Load()),
            args=[],
            keywords=[ast.keyword(arg="value", value=value)],
        )
        return ast.Yield(value=wrapped_value)


class CallTransformer(ast.NodeTransformer):
    """Replace explicit function calls with a gadget that recursively compiles
    functions into generators and then replaces the function call with a
    yield from.

    The transformations are only valid for ASTs that have passed through the
    desugaring pass; only ast.Expr(value=ast.Call(...)) and
    ast.Assign(targets=..., value=ast.Call(..)) nodes are transformed here.
    """

    def visit_Assign(self, node: ast.Assign) -> ast.stmt:
        if not isinstance(node.value, ast.Call):
            return node
        assign_stmt = ast.Assign(targets=node.targets)
        return self._build_call_gadget(node.value, assign_stmt)

    def visit_Expr(self, node: ast.Expr) -> ast.stmt:
        if not isinstance(node.value, ast.Call):
            return node
        return self._build_call_gadget(node.value)

    def _build_call_gadget(
        self, fn_call: ast.Call, assign: ast.Assign | None = None
    ) -> ast.stmt:
        fn = fn_call.func
        args = ast.List(elts=fn_call.args, ctx=ast.Load())
        if fn_call.keywords:
            kwargs: ast.expr = ast.Call(
                func=ast.Name(id="dict", ctx=ast.Load()),
                args=[],
                keywords=fn_call.keywords,
            )
        else:
            kwargs = ast.Constant(value=None)

        compiled_fn = ast.Name(id="_multicolor_compiled_fn", ctx=ast.Store())
        compiled_fn_call = ast.Call(
            func=ast.Name(id="_multicolor_compiled_fn", ctx=ast.Load()),
            args=fn_call.args,
            keywords=fn_call.keywords,
        )

        if assign:
            assign.value = ast.Name(id="_multicolor_result", ctx=ast.Load())
            assign_result: ast.stmt = assign
        else:
            assign_result = ast.Pass()

        result = rewrite_template(
            """
            if hasattr(__fn__, "_multicolor_yield_type"):
                _multicolor_result = yield _multicolor_custom_yield(type=__fn__._multicolor_yield_type, args=__args__, kwargs=__kwargs__)
                __assign_result__
            elif hasattr(__fn__, "_multicolor_no_yields"):
                _multicolor_result = __fn_call__
                __assign_result__
            else:
                _multicolor_result = None
                try:
                    if isinstance(__fn__, type):
                        raise _multicolor_no_source_error # FIXME: this bypasses compilation for calls that are actually class instantiations
                    __compiled_fn__, _multicolor_color = _multicolor_compile(__fn__, _multicolor_decorator, _multicolor_cache_key)
                except _multicolor_no_source_error:
                    _multicolor_result = __fn_call__
                else:
                    _multicolor_generator = __compiled_fn_call__
                    if _multicolor_color == _multicolor_generator_color:
                        _multicolor_result = []
                        for _multicolor_yield in _multicolor_generator:
                            if isinstance(_multicolor_yield, _multicolor_generator_yield):
                                _multicolor_result.append(_multicolor_yield.value)
                            else:
                                yield _multicolor_yield
                    else:
                        _multicolor_result = yield from _multicolor_generator
                finally:
                    __assign_result__
            """,
            __fn__=fn,
            __fn_call__=fn_call,
            __args__=args,
            __kwargs__=kwargs,
            __compiled_fn__=compiled_fn,
            __compiled_fn_call__=compiled_fn_call,
            __assign_result__=assign_result,
        )

        return result[0]
