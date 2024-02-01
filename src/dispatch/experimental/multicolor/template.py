import ast


def rewrite_template(
    template: str, expressions: dict[str, ast.expr], statements: dict[str, ast.stmt]
) -> list[ast.stmt]:
    """Create an AST by parsing a template string and then replacing
    temporary variables with the specified AST nodes."""
    root = ast.parse(template)
    root = NameTransformer(expressions=expressions, statements=statements).visit(root)
    return root.body


class NameTransformer(ast.NodeTransformer):
    """Replace ast.Name nodes in an AST."""

    def __init__(
        self, expressions: dict[str, ast.expr], statements: dict[str, ast.stmt]
    ):
        self.expressions = expressions
        self.statements = statements

    def visit_Name(self, node):
        try:
            return self.expressions[node.id]
        except KeyError:
            return node

    def visit_Expr(self, node):
        if not isinstance(node.value, ast.Name):
            return node
        try:
            return self.statements[node.value.id]
        except KeyError:
            return node
