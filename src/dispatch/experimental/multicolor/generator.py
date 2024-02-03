import ast


def is_generator(fn_def: ast.FunctionDef) -> bool:
    """Returns a boolean indicating whether a function is a
    generator function.

    Args:
        fn_def: A function definition.
    """
    yield_counter = YieldCounter()
    yield_counter.visit(fn_def)
    return yield_counter.count > 0


class YieldCounter(ast.NodeVisitor):
    """AST visitor that walks an ast.FunctionDef to count yield and yield from
    statements.

    The resulting count can be used to determine if the input function is
    a generator or not.

    Yields from nested function/class definitions are not counted.
    """

    def __init__(self):
        self.count = 0
        self.depth = 0

    def visit_Yield(self, node: ast.Yield):
        self.count += 1

    def visit_YieldFrom(self, node: ast.YieldFrom):
        self.count += 1

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_nested(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_nested(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._visit_nested(node)

    def _visit_nested(self, node: ast.stmt):
        self.depth += 1
        if self.depth > 1:
            return  # do not recurse
        self.generic_visit(node)
        self.depth -= 1


def empty_generator():
    """A generator that yields nothing.

    A `yield from` this generator can be inserted into a function definition in
    order to turn the function into a generator, without causing any visible
    side effects.
    """
    if False:
        yield
