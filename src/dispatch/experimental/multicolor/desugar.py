import ast
from typing import cast


def desugar_function(fn_def: ast.FunctionDef) -> ast.FunctionDef:
    """Desugar a function to simplify subsequent AST transformations.

    Args:
        fn_def: A function definition.

    Returns:
        FunctionDef: The desugared function definition.
    """
    fn_def.body = Desugar().desugar(fn_def.body)
    ast.fix_missing_locations(fn_def)
    return fn_def


class Desugar:
    """The desugar pass simplifies subsequent AST transformations that need
    to replace an expression (e.g. a function call) with a statement (e.g. an
    if branch) in a function definition.

    The pass recursively simplifies control flow and compound expressions
    in a function definition such that:
    - expressions that are children of statements either have no children, or
      only have children of type ast.Name and/or ast.Constant
    - those parent expressions are either part of an ast.Expr(value=expr)
      statement or an ast.Assign(value=expr) statement

    The pass does not recurse into lambda expressions, or nested function or
    class definitions.
    """

    def __init__(self):
        self.name_count = 0

    def desugar(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        return self._desugar_stmts(stmts)

    def _desugar_stmt(self, stmt: ast.stmt) -> tuple[ast.stmt, list[ast.stmt]]:
        deps: list[ast.stmt] = []
        match stmt:
            # Pass
            case ast.Pass():
                pass

            # Break
            case ast.Break():
                pass

            # Continue
            case ast.Continue():
                pass

            # Import(alias* names)
            case ast.Import():
                pass

            # ImportFrom(identifier? module, alias* names, int? level)
            case ast.ImportFrom():
                pass

            # Nonlocal(identifier* names)
            case ast.Nonlocal():
                pass

            # Global(identifier* names)
            case ast.Global():
                pass

            # Return(expr? value)
            case ast.Return():
                if stmt.value is not None:
                    stmt.value, deps = self._desugar_expr(stmt.value)

            # Expr(expr value)
            case ast.Expr():
                stmt.value, deps = self._desugar_expr(stmt.value, expr_stmt=True)

            # Assert(expr test, expr? msg)
            case ast.Assert():
                stmt.test, deps = self._desugar_expr(stmt.test)
                if stmt.msg is not None:
                    stmt.msg, msg_deps = self._desugar_expr(stmt.msg)
                    deps.extend(msg_deps)

            # Assign(expr* targets, expr value, string? type_comment)
            case ast.Assign():
                stmt.targets, deps = self._desugar_exprs(stmt.targets)
                stmt.value, value_deps = self._desugar_expr(stmt.value)
                deps.extend(value_deps)

            # AugAssign(expr target, operator op, expr value)
            case ast.AugAssign():
                target = cast(
                    ast.expr, stmt.target
                )  # ast.Name | ast.Attribute | ast.Subscript
                target, deps = self._desugar_expr(target)
                stmt.target = cast(ast.Name | ast.Attribute | ast.Subscript, target)
                stmt.value, value_deps = self._desugar_expr(stmt.value)
                deps.extend(value_deps)

            # AnnAssign(expr target, expr annotation, expr? value, int simple)
            case ast.AnnAssign():
                target = cast(
                    ast.expr, stmt.target
                )  # ast.Name | ast.Attribute | ast.Subscript
                target, deps = self._desugar_expr(target)
                stmt.target = cast(ast.Name | ast.Attribute | ast.Subscript, target)
                stmt.annotation, annotation_deps = self._desugar_expr(stmt.annotation)
                deps.extend(annotation_deps)
                if stmt.value is not None:
                    stmt.value, value_deps = self._desugar_expr(stmt.value)
                    deps.extend(value_deps)

            # Delete(expr* targets)
            case ast.Delete():
                stmt.targets, deps = self._desugar_exprs(stmt.targets, del_stmt=True)

            # Raise(expr? exc, expr? cause)
            case ast.Raise():
                if stmt.exc is not None:
                    stmt.exc, exc_deps = self._desugar_expr(stmt.exc)
                    deps.extend(exc_deps)
                if stmt.cause is not None:
                    stmt.cause, cause_deps = self._desugar_expr(stmt.cause)
                    deps.extend(cause_deps)

            # If(expr test, stmt* body, stmt* orelse)
            case ast.If():
                stmt.test, deps = self._desugar_expr(stmt.test)
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.orelse = self._desugar_stmts(stmt.orelse)

            # While(expr test, stmt* body, stmt* orelse)
            case ast.While():
                stmt.test, deps = self._desugar_expr(stmt.test)
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.orelse = self._desugar_stmts(stmt.orelse)

            # For(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
            case ast.For():
                stmt.target, deps = self._desugar_expr(stmt.target)
                stmt.iter, iter_deps = self._desugar_expr(stmt.iter)
                deps.extend(iter_deps)
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.orelse = self._desugar_stmts(stmt.orelse)

            # AsyncFor(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
            case ast.AsyncFor():
                stmt.target, deps = self._desugar_expr(stmt.target)
                stmt.iter, iter_deps = self._desugar_expr(stmt.iter)
                deps.extend(iter_deps)
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.orelse = self._desugar_stmts(stmt.orelse)

            # Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
            case ast.Try():
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.handlers, deps = self._desugar_except_handlers(stmt.handlers)
                stmt.orelse = self._desugar_stmts(stmt.orelse)
                stmt.finalbody = self._desugar_stmts(stmt.finalbody)

            # TryStar(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
            case ast.TryStar():
                stmt.body = self._desugar_stmts(stmt.body)
                stmt.handlers, deps = self._desugar_except_handlers(stmt.handlers)
                stmt.orelse = self._desugar_stmts(stmt.orelse)
                stmt.finalbody = self._desugar_stmts(stmt.finalbody)

            # Match(expr subject, match_case* cases)
            case ast.Match():
                stmt.subject, deps = self._desugar_expr(stmt.subject)
                stmt.cases, match_case_deps = self._desugar_match_cases(stmt.cases)
                deps.extend(match_case_deps)

            # With(withitem* items, stmt* body, string? type_comment)
            case ast.With():
                while len(stmt.items) > 1:
                    last = stmt.items.pop()
                    stmt.body = [ast.With(items=[last], body=stmt.body)]

                stmt.items, deps = self._desugar_withitems(stmt.items)
                stmt.body = self._desugar_stmts(stmt.body)

            # AsyncWith(withitem* items, stmt* body, string? type_comment)
            case ast.AsyncWith():
                while len(stmt.items) > 1:
                    last = stmt.items.pop()
                    stmt.body = [ast.AsyncWith(items=[last], body=stmt.body)]

                stmt.items, deps = self._desugar_withitems(stmt.items)
                stmt.body = self._desugar_stmts(stmt.body)

            # FunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment)
            case ast.FunctionDef():
                pass  # do not recurse

            # AsyncFunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment)
            case ast.AsyncFunctionDef():
                pass  # do not recurse

            # ClassDef(identifier name, expr* bases, keyword* keywords, stmt* body, expr* decorator_list)
            case ast.ClassDef():
                pass  # do not recurse

            case _:
                raise NotImplementedError(f"desugar {stmt}")

        return stmt, deps

    def _desugar_expr(
        self, expr: ast.expr, expr_stmt=False, del_stmt=False
    ) -> tuple[ast.expr, list[ast.stmt]]:
        # These cases have no nested expressions or statements. Return
        # early so that no superfluous temporaries are generated.
        if isinstance(expr, ast.Name):
            # Name(identifier id, expr_context ctx)
            return expr, []
        elif isinstance(expr, ast.Constant):
            # Constant(constant value, string? kind)
            return expr, []
        elif isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            # Attribute(expr value, identifier attr, expr_context ctx)
            return expr, []

        deps: list[ast.stmt] = []
        wrapper = None
        create_temporary = not expr_stmt and not del_stmt
        is_store = False
        match expr:
            # Call(expr func, expr* args, keyword* keywords)
            case ast.Call():
                expr.func, deps = self._desugar_expr(expr.func)
                expr.args, args_deps = self._desugar_exprs(expr.args)
                deps.extend(args_deps)
                expr.keywords, keywords_deps = self._desugar_keywords(expr.keywords)
                deps.extend(keywords_deps)

            # BinOp(expr left, operator op, expr right)
            case ast.BinOp():
                expr.left, deps = self._desugar_expr(expr.left)
                expr.right, right_deps = self._desugar_expr(expr.right)
                deps.extend(right_deps)

            # UnaryOp(unaryop op, expr operand)
            case ast.UnaryOp():
                expr.operand, deps = self._desugar_expr(expr.operand)

            # BoolOp(boolop op, expr* values)
            case ast.BoolOp():
                expr.values, deps = self._desugar_exprs(expr.values)

            # Tuple(expr* elts, expr_context ctx)
            case ast.Tuple():
                expr.elts, deps = self._desugar_exprs(expr.elts)
                is_store = isinstance(expr.ctx, ast.Store)

            # List(expr* elts, expr_context ctx)
            case ast.List():
                expr.elts, deps = self._desugar_exprs(expr.elts)
                is_store = isinstance(expr.ctx, ast.Store)

            # Set(expr* elts)
            case ast.Set():
                expr.elts, deps = self._desugar_exprs(expr.elts)

            # Dict(expr* keys, expr* values)
            case ast.Dict():
                for i, key in enumerate(expr.keys):
                    if key is not None:
                        key, key_deps = self._desugar_expr(key)
                        deps.extend(key_deps)
                    expr.keys[i] = key
                expr.values, values_deps = self._desugar_exprs(expr.values)
                deps.extend(values_deps)

            # Starred(expr value, expr_context ctx)
            case ast.Starred():
                expr.value, deps = self._desugar_expr(expr.value)
                is_store = isinstance(expr.ctx, ast.Store)
                create_temporary = False

            # Compare(expr left, cmpop* ops, expr* comparators)
            case ast.Compare():
                expr.left, deps = self._desugar_expr(expr.left)
                expr.comparators, comparators_deps = self._desugar_exprs(
                    expr.comparators
                )
                deps.extend(comparators_deps)

            # NamedExpr(expr target, expr value)
            case ast.NamedExpr():
                target = cast(ast.expr, expr.target)  # ast.Name
                target, deps = self._desugar_expr(target)
                expr.target = cast(ast.Name, target)
                expr.value, value_deps = self._desugar_expr(expr.value)
                deps.extend(value_deps)

                # We need to preserve the assignment so that the target is accessible
                # from subsequent expressions/statements. ast.NamedExpr isn't valid as
                # a standalone a statement, so we need to convert to ast.Assign.
                deps.append(ast.Assign(targets=[expr.target], value=expr.value))
                expr = expr.target

            # Lambda(arguments args, expr body)
            case ast.Lambda():
                pass  # do not recurse

            # Await(expr value)
            case ast.Await():
                expr.value, deps = self._desugar_expr(expr.value)

            # Yield(expr? value)
            case ast.Yield():
                if expr.value is not None:
                    expr.value, deps = self._desugar_expr(expr.value)

            # YieldFrom(expr value)
            case ast.YieldFrom():
                expr.value, deps = self._desugar_expr(expr.value)

            # JoinedStr(expr* values)
            case ast.JoinedStr():
                expr.values, deps = self._desugar_exprs(expr.values)

            # FormattedValue(expr value, int conversion, expr? format_spec)
            case ast.FormattedValue():
                expr.value, deps = self._desugar_expr(expr.value)
                # Note: expr.format_spec is an expression, but we do not expect to
                # find compound expressions there.

                conversion = expr.conversion
                format_spec = expr.format_spec
                expr = expr.value
                create_temporary = False

                def wrapper(value):
                    return ast.FormattedValue(
                        value=value, conversion=conversion, format_spec=format_spec
                    )

            # Attribute(expr value, identifier attr, expr_context ctx)
            case ast.Attribute():
                expr.value, deps = self._desugar_expr(expr.value)
                is_store = isinstance(expr.ctx, ast.Store)

            # Subscript(expr value, expr slice, expr_context ctx)
            case ast.Subscript():
                expr.value, deps = self._desugar_expr(expr.value)
                expr.slice, slice_deps = self._desugar_expr(expr.slice)
                deps.extend(slice_deps)
                is_store = isinstance(expr.ctx, ast.Store)

            # Slice(expr? lower, expr? upper, expr? step)
            case ast.Slice():
                if expr.lower is not None:
                    expr.lower, lower_deps = self._desugar_expr(expr.lower)
                    deps.extend(lower_deps)
                if expr.upper is not None:
                    expr.upper, upper_deps = self._desugar_expr(expr.upper)
                    deps.extend(upper_deps)
                if expr.step is not None:
                    expr.step, step_deps = self._desugar_expr(expr.step)
                    deps.extend(step_deps)
                is_store = True

            # IfExp(expr test, expr body, expr orelse)
            case ast.IfExp():
                tmp = self._new_name()
                if_stmt, deps = self._desugar_stmt(
                    ast.If(
                        test=expr.test,
                        body=[
                            ast.Assign(
                                targets=[ast.Name(id=tmp, ctx=ast.Store())],
                                value=expr.body,
                            )
                        ],
                        orelse=[
                            ast.Assign(
                                targets=[ast.Name(id=tmp, ctx=ast.Store())],
                                value=expr.orelse,
                            )
                        ],
                    )
                )
                deps.append(if_stmt)
                expr = ast.Name(id=tmp, ctx=ast.Load())
                create_temporary = False

            # ListComp(expr elt, comprehension* generators)
            case ast.ListComp():
                tmp = self._new_name()

                deps = [
                    ast.Assign(
                        targets=[ast.Name(id=tmp, ctx=ast.Store())],
                        value=ast.List(elts=[], ctx=ast.Load()),
                    )
                ]

                inner_statement: ast.stmt = ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=tmp, ctx=ast.Load()),
                            attr="append",
                            ctx=ast.Load(),
                        ),
                        args=[expr.elt],
                        keywords=[],
                    )
                )

                deps += self._desugar_comprehensions(expr.generators, inner_statement)
                expr = ast.Name(id=tmp, ctx=ast.Load())
                create_temporary = False

            # SetComp(expr elt, comprehension* generators)
            case ast.SetComp():
                tmp = self._new_name()

                deps = [
                    ast.Assign(
                        targets=[ast.Name(id=tmp, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="set", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        ),
                    )
                ]

                inner_statement = ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=tmp, ctx=ast.Load()),
                            attr="add",
                            ctx=ast.Load(),
                        ),
                        args=[expr.elt],
                        keywords=[],
                    )
                )

                deps += self._desugar_comprehensions(expr.generators, inner_statement)
                expr = ast.Name(id=tmp, ctx=ast.Load())
                create_temporary = False

            # DictComp(expr key, expr value, comprehension* generators)
            case ast.DictComp():
                tmp = self._new_name()

                deps = [
                    ast.Assign(
                        targets=[ast.Name(id=tmp, ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ]

                inner_statement = ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id=tmp, ctx=ast.Store()),
                            slice=expr.key,
                            ctx=ast.Store(),
                        )
                    ],
                    value=expr.value,
                )

                deps += self._desugar_comprehensions(expr.generators, inner_statement)
                expr = ast.Name(id=tmp, ctx=ast.Load())
                create_temporary = False

            # GeneratorExp(expr elt, comprehension* generators)
            case ast.GeneratorExp():
                tmp = self._new_name()
                inner_statement = ast.Expr(value=ast.Yield(value=expr.elt))
                body = self._desugar_comprehensions(expr.generators, inner_statement)
                deps = [
                    ast.FunctionDef(
                        name=tmp,
                        args=ast.arguments(
                            args=[],
                            posonlyargs=[],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=body,
                        decorator_list=[],
                    )
                ]
                expr = ast.Call(
                    func=ast.Name(id=tmp, ctx=ast.Load()), args=[], keywords=[]
                )

            case _:
                raise NotImplementedError(f"desugar {expr}")

        if create_temporary and not is_store:
            tmp = self._new_name()
            deps.append(
                ast.Assign(targets=[ast.Name(id=tmp, ctx=ast.Store())], value=expr)
            )
            expr = ast.Name(id=tmp, ctx=ast.Load())

        if wrapper is not None:
            expr = wrapper(expr)

        return expr, deps

    def _desugar_stmts(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        desugared = []
        for stmt in stmts:
            stmt, deps = self._desugar_stmt(stmt)
            desugared.extend(deps)
            desugared.append(stmt)
        return desugared

    def _desugar_exprs(
        self, exprs: list[ast.expr], del_stmt=False
    ) -> tuple[list[ast.expr], list[ast.stmt]]:
        desugared = []
        deps = []
        for expr in exprs:
            expr, expr_deps = self._desugar_expr(expr, del_stmt=del_stmt)
            deps.extend(expr_deps)
            desugared.append(expr)
        return desugared, deps

    def _desugar_keywords(
        self, keywords: list[ast.keyword]
    ) -> tuple[list[ast.keyword], list[ast.stmt]]:
        # keyword(identifier? arg, expr value)
        desugared = []
        deps = []
        for keyword in keywords:
            keyword.value, keyword_deps = self._desugar_expr(keyword.value)
            deps.extend(keyword_deps)
            desugared.append(keyword)
        return desugared, deps

    def _desugar_except_handlers(
        self, handlers: list[ast.ExceptHandler]
    ) -> tuple[list[ast.ExceptHandler], list[ast.stmt]]:
        # excepthandler = ExceptHandler(expr? type, identifier? name, stmt* body)
        desugared = []
        deps: list[ast.stmt] = []
        for handler in handlers:
            if handler.type is not None:
                # FIXME: exception type exprs need special handling. Each handler's
                #  type expr is evaluated one at a time until there's a match. The
                #  remaining handler's type exprs are not evaluated.
                # handler.type, type_deps = self._desugar_expr(handler.type)
                # deps.extend(type_deps)
                pass
            handler.body = self._desugar_stmts(handler.body)
            desugared.append(handler)
        return desugared, deps

    def _desugar_match_cases(
        self, cases: list[ast.match_case]
    ) -> tuple[list[ast.match_case], list[ast.stmt]]:
        # match_case(pattern pattern, expr? guard, stmt* body)
        desugared: list[ast.match_case] = []
        deps: list[ast.stmt] = []
        for case in cases:
            if case.guard is not None:
                # FIXME: match guards need special handling; they shouldn't be evaluated
                #  unless the pattern matches.
                # case.guard, guard_deps = self._desugar_expr(case.guard)
                # deps.extend(guard_deps)
                pass
            case.body = self._desugar_stmts(case.body)
            desugared.append(case)
            # You're supposed to be able to pass the AST root to this function
            # to have it repair (fill in missing) line numbers and such. It
            # seems there's a bug where it doesn't recurse into match cases.
            # Work around the issue by manually fixing the match case here.
            ast.fix_missing_locations(case)
        return desugared, deps

    def _desugar_withitems(
        self, withitems: list[ast.withitem]
    ) -> tuple[list[ast.withitem], list[ast.stmt]]:
        # withitem(expr context_expr, expr? optional_vars)
        desugared = []
        deps = []
        for withitem in withitems:
            withitem.context_expr, context_expr_deps = self._desugar_expr(
                withitem.context_expr
            )
            deps.extend(context_expr_deps)
            if withitem.optional_vars is not None:
                withitem.optional_vars, optional_vars_deps = self._desugar_expr(
                    withitem.optional_vars
                )
                deps.extend(optional_vars_deps)
            desugared.append(withitem)
        return desugared, deps

    def _desugar_comprehensions(
        self, comprehensions: list[ast.comprehension], inner_statement: ast.stmt
    ) -> list[ast.stmt]:
        # comprehension(expr target, expr iter, expr* ifs, int is_async)
        stmt = inner_statement
        while comprehensions:
            last_for = comprehensions.pop()
            while last_for.ifs:
                test = last_for.ifs.pop()
                stmt = ast.If(test=test, body=[stmt], orelse=[])
            cls = ast.AsyncFor if last_for.is_async else ast.For
            stmt = cls(
                target=last_for.target, iter=last_for.iter, body=[stmt], orelse=[]
            )

        stmt, deps = self._desugar_stmt(stmt)
        return deps + [stmt]

    def _new_name(self) -> str:
        name = f"_v{self.name_count}"
        self.name_count += 1
        return name
