import ast
import textwrap


def rewrite_template(
    template: str, **replacements: ast.expr | ast.stmt
) -> list[ast.stmt]:
    """Create an AST by parsing a template string and then replacing
    embedded identifiers with the provided AST nodes.

    Args:
        template: String containing source code (one or more statements).
        **replacements: Dictionary mapping identifiers to replacement nodes.

    Returns:
        list[ast.stmt]: List of AST statements.
    """
    root = ast.parse(textwrap.dedent(template))
    root = NameTransformer(**replacements).visit(root)
    return root.body


class NameTransformer(ast.NodeTransformer):
    """Replace ast.Name nodes in an AST."""

    exprs: dict[str, ast.expr]
    stmts: dict[str, ast.stmt]

    def __init__(self, **replacements: ast.expr | ast.stmt):
        self.exprs = {}
        self.stmts = {}
        for key, node in replacements.items():
            if isinstance(node, ast.expr):
                self.exprs[key] = node
            elif isinstance(node, ast.stmt):
                self.stmts[key] = node

    def visit_Name(self, node: ast.Name) -> ast.expr:
        try:
            return self.exprs[node.id]
        except KeyError:
            return node

    def visit_Expr(self, node: ast.Expr) -> ast.stmt:
        if not isinstance(node.value, ast.Name):
            return node
        try:
            return self.stmts[node.value.id]
        except KeyError:
            return node
