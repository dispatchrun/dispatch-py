import ast
import unittest
from types import FunctionType

from dispatch.experimental.multicolor.desugar import desugar_function
from dispatch.experimental.multicolor.parse import parse_function

# Disable lint checks:
# ruff: noqa


class TestDesugar(unittest.TestCase):
    def test_pass(self):
        def fn():
            pass

        self.assert_desugar_is_noop(fn)

    def test_import(self):
        def fn():
            import ast

        self.assert_desugar_is_noop(fn)

    def test_import_from(self):
        def fn():
            from ast import parse

        self.assert_desugar_is_noop(fn)

    def test_global(self):
        def fn():
            global ast

        self.assert_desugar_is_noop(fn)

    def test_expr_stmt(self):
        def fn():
            identity(1)

        self.assert_desugar_is_noop(fn)

    def test_return_empty(self):
        def fn():
            return

        self.assert_desugar_is_noop(fn)

    def test_return_call(self):
        def before():
            return identity(1)

        def after():
            _v0 = identity(1)
            return _v0

        self.assert_desugared(before, after)

    def test_return_bin_op(self):
        def before():
            return identity(1) + identity(2)

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = _v0 + _v1
            return _v2

        self.assert_desugared(before, after)

    def test_return_unary_op(self):
        def before():
            return not identity(1)

        def after():
            _v0 = identity(1)
            _v1 = not _v0
            return _v1

        self.assert_desugared(before, after)

    def test_return_bool_op(self):
        def before():
            return identity(1) and identity(2)

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = _v0 and _v1
            return _v2

        self.assert_desugared(before, after)

    def test_compound_literals(self):
        def before():
            foo = [identity(1), identity(2), *identity(3)]
            bar = {identity(4)}
            baz = {identity(5): identity(6), **identity(7)}

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = identity(3)
            _v3 = [_v0, _v1, *_v2]
            foo = _v3
            _v4 = identity(4)
            _v5 = {_v4}
            bar = _v5
            _v6 = identity(5)
            _v7 = identity(6)
            _v8 = identity(7)
            _v9 = {_v6: _v7, **_v8}
            baz = _v9

        self.assert_desugared(before, after)

    def test_assert_bool(self):
        def fn():
            assert True
            assert True, "message"

        self.assert_desugar_is_noop(fn)

    def test_assert_call(self):
        def before():
            assert identity(1)
            assert identity(2), "message"
            assert identity(3), identity(4)

        def after():
            _v0 = identity(1)
            assert _v0
            _v1 = identity(2)
            assert _v1, "message"
            _v2 = identity(3)
            _v3 = identity(4)
            assert _v2, _v3

        self.assert_desugared(before, after)

    def test_assign_name_constant(self):
        def fn():
            foo = 1
            bar: int = 1  # type: ignore[annotation-unchecked]
            foo += 1

        self.assert_desugar_is_noop(fn)

    def test_assign_call(self):
        def before():
            foo = identity(1)
            bar: int = identity(2)  # type: ignore[annotation-unchecked]
            foo += identity(3)

        def after():
            _v0 = identity(1)
            foo = _v0
            _v1 = identity(2)
            bar: int = _v1  # type: ignore[annotation-unchecked]
            _v2 = identity(3)
            foo += _v2

        self.assert_desugared(before, after)

    def test_assign_tuple(self):
        def before():
            foo, bar = 1, 2

        def after():
            _v0 = (1, 2)
            foo, bar = _v0

        self.assert_desugared(before, after)

    def test_assign_tuple_call(self):
        def before():
            foo, bar = identity(1), identity(2)

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = (_v0, _v1)
            foo, bar = _v2

        self.assert_desugared(before, after)

    def test_if_noops(self):
        def fn():
            if True:
                pass
            if False:
                pass
            elif True:
                pass
            if True:
                pass
            elif True:
                pass
            else:
                pass

        self.assert_desugar_is_noop(fn)

    def test_if(self):
        def before():
            if identity(1) == 1:
                return identity(2)
            else:
                return identity(3)

        def after():
            _v0 = identity(1)
            _v1 = _v0 == 1
            if _v1:
                _v2 = identity(2)
                return _v2
            else:
                _v3 = identity(3)
                return _v3

        self.assert_desugared(before, after)

    def test_nested_ifs(self):
        def before():
            if identity(1) == 1:
                return identity(2)
            elif identity(3) == 3:
                return identity(4)
            else:
                return identity(5)

        def after():
            _v0 = identity(1)
            _v1 = _v0 == 1
            if _v1:
                _v2 = identity(2)
                return _v2
            else:
                _v3 = identity(3)
                _v4 = _v3 == 3
                if _v4:
                    _v5 = identity(4)
                    return _v5
                else:
                    _v6 = identity(5)
                    return _v6

        self.assert_desugared(before, after)

    def test_named_expr(self):
        def before():
            if (n := identity(1)) == 1:
                return n

        def after():
            _v0 = identity(1)
            n = _v0
            _v1 = n
            _v2 = _v1 == 1
            if _v2:
                return n

        self.assert_desugared(before, after)

    def test_while_noops(self):
        def fn():
            while True:
                break
            while False:
                continue
            else:
                return

        self.assert_desugar_is_noop(fn)

    def test_while(self):
        def before():
            while identity(1) == identity(2):
                return identity(3)
            else:
                return identity(4)

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = _v0 == _v1
            while _v2:
                _v3 = identity(3)
                return _v3
            else:
                _v4 = identity(4)
                return _v4

        self.assert_desugared(before, after)

    def test_for_noops(self):
        def fn(x=[]):
            for i in x:
                pass
            for i in x:
                break
            else:
                return

        self.assert_desugar_is_noop(fn)

    def test_for(self):
        def before():
            for i, x in enumerate(identity(1)):
                return identity(2)
            else:
                return identity(3)

        def after():
            _v0 = identity(1)
            _v1 = enumerate(_v0)
            for i, x in _v1:
                _v2 = identity(2)
                return _v2
            else:
                _v3 = identity(3)
                return _v3

        self.assert_desugared(before, after)

    def test_async_for_noops(self):
        async def fn(x=[]):
            async for i in x:
                pass
            async for i in x:
                break
            else:
                return

        self.assert_desugar_is_noop(fn)

    def test_async_for(self):
        async def before():
            async for i, x in identity(1):
                return identity(2)
            else:
                return identity(3)

        async def after():
            _v0 = identity(1)
            async for i, x in _v0:
                _v1 = identity(2)
                return _v1
            else:
                _v2 = identity(3)
                return _v2

        self.assert_desugared(before, after)

    def test_try(self):
        def before():
            try:
                return identity(1)
            except RuntimeError as e:
                return identity(2)
            else:
                return identity(3)
            finally:
                return identity(4)

        def after():
            try:
                _v0 = identity(1)
                return _v0
            except RuntimeError as e:
                _v1 = identity(2)
                return _v1
            else:
                _v2 = identity(3)
                return _v2
            finally:
                _v3 = identity(4)
                return _v3

        self.assert_desugared(before, after)

    def test_try_type_expr(self):
        def before():
            try:
                pass
            except RuntimeError as a:
                pass
            except identity(1) as b:
                pass

        def after():
            try:
                pass
            except RuntimeError as a:
                pass
            except identity(1) as b:  # FIXME: desugar the type expr
                pass

        self.assert_desugared(before, after)

    def test_match(self):
        def before():
            match identity(1):
                case ast.Expr():
                    return identity(3)
                case ast.Call() if identity(2):
                    pass

        def after():
            _v0 = identity(1)
            match _v0:
                case ast.Expr():  # this is a pattern, not an expression
                    _v1 = identity(3)
                    return _v1
                case ast.Call() if identity(2):  # FIXME: desugar the guard
                    pass

        self.assert_desugared(before, after)

    def test_with(self):
        def before():
            with identity(1) as x:
                return identity(2)

        def after():
            _v0 = identity(1)
            with _v0 as x:
                _v1 = identity(2)
                return _v1

        self.assert_desugared(before, after)

    def test_nested_with(self):
        def before():
            with identity(1) as x, identity(x) as y, identity(y) as z:
                return identity(2)

        def after():
            _v0 = identity(1)
            with _v0 as x:
                _v1 = identity(x)
                with _v1 as y:
                    _v2 = identity(y)
                    with _v2 as z:
                        _v3 = identity(2)
                        return _v3

        self.assert_desugared(before, after)

    def test_async_with(self):
        async def before():
            async with identity(1) as x:
                return identity(2)

        async def after():
            _v0 = identity(1)
            async with _v0 as x:
                _v1 = identity(2)
                return _v1

        self.assert_desugared(before, after)

    def test_nested_async_with(self):
        async def before():
            async with identity(1) as x, identity(x) as y, identity(y) as z:
                return identity(2)

        async def after():
            _v0 = identity(1)
            async with _v0 as x:
                _v1 = identity(x)
                async with _v1 as y:
                    _v2 = identity(y)
                    async with _v2 as z:
                        _v3 = identity(2)
                        return _v3

        self.assert_desugared(before, after)

    def test_await(self):
        async def before():
            return await identity(1)

        async def after():
            _v0 = identity(1)
            _v1 = await _v0
            return _v1

        self.assert_desugared(before, after)

    def test_yield(self):
        def before():
            yield
            yield identity(1)
            return (yield identity(2))

        def after():
            yield
            _v0 = identity(1)
            yield _v0
            _v1 = identity(2)
            _v2 = yield _v1
            return _v2

        self.assert_desugared(before, after)

    def test_yield_from(self):
        def before():
            yield from identity(1)
            return (yield from identity(2))

        def after():
            _v0 = identity(1)
            yield from _v0
            _v1 = identity(2)
            _v2 = yield from _v1
            return _v2

        self.assert_desugared(before, after)

    def test_f_strings(self):
        def before():
            print(f"a {identity(1)} b {identity(2)} c")

        def after():
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = f"a {_v0} b {_v1} c"
            print(_v2)

        self.assert_desugared(before, after)

    def test_attribute(self):
        def before(a):
            foo = a.b

            a.b = True

            foo = identity(1).foo
            identity(2).foo = True

        def after(a):
            foo = a.b

            a.b = True

            _v0 = identity(1)
            _v1 = _v0.foo
            foo = _v1

            _v2 = identity(2)
            _v2.foo = True

        self.assert_desugared(before, after)

    def test_subscript(self):
        def before(a, b):
            foo = a[b]

            a[b] = True

            foo = identity(1)[identity(2)]

            identity(3)[identity(4)] = True

        def after(a, b):
            _v0 = a[b]
            foo = _v0

            a[b] = True

            _v1 = identity(1)
            _v2 = identity(2)
            _v3 = _v1[_v2]
            foo = _v3

            _v4 = identity(3)
            _v5 = identity(4)
            _v4[_v5] = True

        self.assert_desugared(before, after)

    def test_slice(self):
        def before(a):
            foo = a[identity(1) : identity(2) : identity(3)]

        def after(a):
            _v0 = identity(1)
            _v1 = identity(2)
            _v2 = identity(3)
            _v3 = a[_v0:_v1:_v2]
            foo = _v3

        self.assert_desugared(before, after)

    def test_store_ctx(self):
        def fn(a):
            [foo] = a
            [*foo] = a
            foo = a
            foo.bar = a
            foo, bar = a
            foo[bar] = a

        self.assert_desugar_is_noop(fn)

    def test_if_expr(self):
        def before():
            foo = identity(2) if identity(1) == 1 else identity(3)

        def after():
            _v1 = identity(1)
            _v2 = _v1 == 1
            if _v2:
                _v3 = identity(2)
                _v0 = _v3
            else:
                _v4 = identity(3)
                _v0 = _v4
            foo = _v0

        self.assert_desugared(before, after)

    def test_list_comprehensions(self):
        def before(y):
            foo = [
                identity(z)
                for x in y
                if x == 1
                if x != 2
                for z in identity(x)
                if identity(z) == 3
            ]

        def after(y):
            _v0 = []
            for x in y:
                _v1 = x == 1
                if _v1:
                    _v2 = x != 2
                    if _v2:
                        _v3 = identity(x)
                        for z in _v3:
                            _v4 = identity(z)
                            _v5 = _v4 == 3
                            if _v5:
                                _v6 = identity(z)
                                _v0.append(_v6)
            foo = _v0

        self.assert_desugared(before, after)

    def test_set_comprehension(self):
        def before(y):
            foo = {
                identity(z)
                for x in y
                if x == 1
                if x != 2
                for z in identity(x)
                if identity(z) == 3
            }

        def after(y):
            _v0 = set()
            for x in y:
                _v1 = x == 1
                if _v1:
                    _v2 = x != 2
                    if _v2:
                        _v3 = identity(x)
                        for z in _v3:
                            _v4 = identity(z)
                            _v5 = _v4 == 3
                            if _v5:
                                _v6 = identity(z)
                                _v0.add(_v6)
            foo = _v0

        self.assert_desugared(before, after)

    def test_dict_comprehension(self):
        self.maxDiff = 10000

        def before(y):
            foo = {
                identity(z): identity(x)
                for x in y
                if x == 1
                if x != 2
                for z in identity(x)
                if identity(z) == 3
            }

        def after(y):
            _v0 = {}
            for x in y:
                _v1 = x == 1
                if _v1:
                    _v2 = x != 2
                    if _v2:
                        _v3 = identity(x)
                        for z in _v3:
                            _v4 = identity(z)
                            _v5 = _v4 == 3
                            if _v5:
                                _v6 = identity(z)
                                _v7 = identity(x)
                                _v0[_v6] = _v7
            foo = _v0

        self.assert_desugared(before, after)

    def test_generator_comprehension(self):
        def before(y):
            foo = (identity(x) for x in y if x == 1)

        def after(y):
            def _v0():
                for x in y:
                    _v1 = x == 1
                    if _v1:
                        _v2 = identity(x)
                        yield _v2

            _v3 = _v0()
            foo = _v3

        self.assert_desugared(before, after)

    def assert_desugar_is_noop(self, fn):
        self.assert_desugared(fn, fn)

    def assert_desugared(self, before: FunctionType, after: FunctionType):
        _, before_def = parse_function(before)
        _, after_def = parse_function(after)

        before_def.name = "function"
        after_def.name = "function"

        desugar_function(before_def)

        expect = ast.unparse(after_def)
        actual = ast.unparse(before_def)
        self.assertEqual(expect, actual)


def identity(x):
    return x
