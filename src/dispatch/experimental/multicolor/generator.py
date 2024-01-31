import ast


def is_generator(fn_def: ast.FunctionDef) -> bool:
    """Check if a function definition defines a generator."""
    yield_counter = YieldCounter()
    yield_counter.visit(fn_def)
    return yield_counter.count > 0


class YieldCounter(ast.NodeVisitor):
    """Walks an ast.FunctionDef to count yield and yield from statements.

    Yields from nested function/class definitions are not counted.

    The resulting count can be used to determine if the input function is
    a generator or not."""

    def __init__(self):
        self.count = 0
        self.depth = 0

    def visit_Yield(self, node):
        self.count += 1

    def visit_YieldFrom(self, node):
        self.count += 1

    def visit_FunctionDef(self, node):
        self._visit_nested(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_nested(node)

    def visit_ClassDef(self, node):
        self._visit_nested(node)

    def _visit_nested(self, node):
        self.depth += 1
        if self.depth > 1:
            return  # do not recurse
        self.generic_visit(node)
        self.depth -= 1


def empty_generator():
    if False:
        yield
