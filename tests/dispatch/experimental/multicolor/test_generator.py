import unittest
from dispatch.experimental.multicolor.parse import parse_function
from dispatch.experimental.multicolor.generator import YieldCounter, is_generator


class TestYieldCounter(unittest.TestCase):
    def test_empty(self):
        def empty():
            pass

        self.assert_yield_count(empty, 0)

    def test_yield(self):
        def yields():
            yield 1
            if True:
                yield 2
            else:
                yield 3

        self.assert_yield_count(yields, 3)

    def test_yield_from(self):
        def yields():
            yield from yields()

        self.assert_yield_count(yields, 1)

    def test_nested_function(self):
        def not_a_generator():
            def nested():
                yield 1

            return 0

        self.assert_yield_count(not_a_generator, 0)

    def test_nested_async_function(self):
        def not_a_generator():
            async def nested():
                yield 1

            return 0

        self.assert_yield_count(not_a_generator, 0)

    def test_nested_class(self):
        def not_a_generator():
            class foo:
                def nested(self):
                    yield 1

            return 0

        self.assert_yield_count(not_a_generator, 0)

    def assert_yield_count(self, fn, count):
        _, fn_def = parse_function(fn)
        yield_counter = YieldCounter()
        yield_counter.visit(fn_def)
        self.assertEqual(yield_counter.count, count)

        self.assertEqual(is_generator(fn_def), count > 0)
