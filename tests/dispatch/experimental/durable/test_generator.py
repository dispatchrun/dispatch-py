import pickle
import types
import unittest
import warnings

from dispatch.experimental.durable import durable


@durable
def durable_generator(a):
    yield a
    a += 1
    yield a
    a += 1
    yield a


@durable
def nested_generators(start):
    yield from durable_generator(start)
    yield from durable_generator(start + 3)


class TestGenerator(unittest.TestCase):
    def test_pickle(self):
        # Create an instance and run it to the first yield point.
        g = durable_generator(1)
        assert next(g) == 1

        # Copy the generator by serializing the DurableGenerator instance to bytes
        # and back.
        state = pickle.dumps(g)
        g2 = pickle.loads(state)

        # The copy should start from where the previous generator was suspended.
        assert next(g2) == 2
        assert next(g2) == 3

        # The original generator is not affected.
        assert next(g) == 2
        assert next(g) == 3

    def test_multiple_references(self):
        g = durable_generator(1)
        assert next(g) == 1

        state = pickle.dumps((g, g))
        g2, g3 = pickle.loads(state)

        self.assertIs(g2, g3)
        self.assertIs(g2.generator, g3.generator)
        assert next(g2) == 2
        assert next(g3) == 3

    def test_multiple_stack_references(self):
        @durable
        def nested():
            g = durable_generator(1)
            g2 = g
            yield next(g)
            yield next(g2)
            yield next(g)

        g = nested()
        self.assertEqual(next(g), 1)
        g2 = pickle.loads(pickle.dumps(g))
        self.assertListEqual(list(g2), [2, 3])

    def test_nested(self):
        expect = [1, 2, 3, 4, 5, 6]
        assert list(nested_generators(1)) == expect

        # Check that the generator can be pickled at every yield point.
        for i in range(len(expect)):
            # Create a generator and advance to the i'th yield point.
            g = nested_generators(1)
            for j in range(i):
                assert next(g) == expect[j]

            # Create a copy of the generator.
            state = pickle.dumps(g)
            g2 = pickle.loads(state)

            # Check that both the original and the copy yield the
            # remaining expected values.
            for j in range(i, len(expect)):
                assert next(g) == expect[j]
                assert next(g2) == expect[j]

    def test_export_gi_fields(self):
        g = nested_generators(1)
        underlying = g.generator

        self.assertIsInstance(g.gi_frame, types.FrameType)
        self.assertIs(g.gi_frame, underlying.gi_frame)

        self.assertIsInstance(g.gi_code, types.CodeType)
        self.assertIs(g.gi_code, underlying.gi_code)

        def check():
            self.assertEqual(g.gi_running, underlying.gi_running)
            self.assertEqual(g.gi_suspended, underlying.gi_suspended)
            self.assertIs(g.gi_yieldfrom, underlying.gi_yieldfrom)

        check()
        for _ in g:
            check()
        check()

    def test_name_conflict(self):
        @durable
        def durable_generator():
            yield 1

        with self.assertRaises(ValueError):

            @durable
            def durable_generator():
                yield 2

    def test_two_way(self):
        @durable
        def two_way(a):
            b = yield a * 10
            c = yield b * 10
            return (yield c * 10)

        input = 1
        sends = [2, 3, 4]
        yields = [10, 20, 30]
        output = 4

        g = two_way(1)

        actual_yields = []
        actual_return = None

        try:
            i = 0
            send = None
            while True:
                next_value = g.send(send)
                actual_yields.append(next_value)
                send = sends[i]
                i += 1
        except StopIteration as e:
            actual_return = e.value

        self.assertEqual(actual_yields, yields)
        self.assertEqual(actual_return, output)

    def test_throw(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)  # FIXME

        ok = False

        @durable
        def check_throw():
            try:
                yield
            except RuntimeError:
                nonlocal ok
                ok = True

        g = check_throw()
        next(g)
        try:
            g.throw(RuntimeError)
        except StopIteration:
            pass
        self.assertTrue(ok)

    def test_close(self):
        ok = False

        @durable
        def check_close():
            try:
                yield
            except GeneratorExit:
                nonlocal ok
                ok = True
                raise

        g = check_close()
        next(g)
        g.close()
        self.assertTrue(ok)

    def test_regular_function(self):
        @durable
        def regular_function():
            return 1

        self.assertEqual(1, regular_function())

    def test_asynchronous_generator(self):
        @durable
        async def async_generator():
            yield

        with self.assertRaises(NotImplementedError):
            async_generator()
