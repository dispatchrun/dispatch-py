import textwrap
import unittest
import ast
from typing import cast
from dispatch.experimental.multicolor.template import rewrite_template


class TestTemplate(unittest.TestCase):
    def test_rewrite_template(self):
        self.assert_rewrite(
            """
        a
        b = c
        """,
            dict(
                a=ast.Expr(ast.Name(id="d", ctx=ast.Load())),
                c=ast.Name(id="e", ctx=ast.Load()),
            ),
            """
        d
        b = e
        """,
        )

    def assert_rewrite(
        self, template: str, replacements: dict[str, ast.expr | ast.stmt], want: str
    ):
        result = rewrite_template(template, **replacements)
        self.assertEqual(
            ast.unparse(cast(ast.AST, result)), textwrap.dedent(want).strip()
        )
