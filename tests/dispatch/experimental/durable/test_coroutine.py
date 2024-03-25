import pickle
import unittest
import warnings
from types import CodeType, FrameType, coroutine

from dispatch.experimental.durable import durable


@coroutine
@durable
def yields(n):
    return (yield n)


@durable
async def durable_coroutine(a):
    await yields(a)
    a += 1
    await yields(a)
    a += 1
    await yields(a)


@durable
async def nested_coroutines(start):
    await durable_coroutine(start)
    await durable_coroutine(start + 3)


class TestCoroutine(unittest.TestCase):
    def test_pickle(self):
        # Create an instance and run it to the first yield point.
        c = durable_coroutine(1)
        g = c.__await__()
        assert next(g) == 1

        # Copy the coroutine by serializing the DurableCoroutine instance to bytes
        # and back.
        state = pickle.dumps(c)
        c2 = pickle.loads(state)
        g2 = c2.__await__()

        # The copy should start from where the previous coroutine was suspended.
        assert next(g2) == 2
        assert next(g2) == 3

        # The original coroutine is not affected.
        assert next(g) == 2
        assert next(g) == 3

    def test_nested(self):
        expect = [1, 2, 3, 4, 5, 6]
        c = nested_coroutines(1)
        g = c.__await__()
        assert list(g) == expect

        # Check that the coroutine can be pickled at every yield point.
        for i in range(len(expect)):
            # Create a coroutine and advance to the i'th yield point.
            c = nested_coroutines(1)
            g = c.__await__()
            for j in range(i):
                assert next(g) == expect[j]

            # Create a copy of the coroutine.
            state = pickle.dumps(c)
            c2 = pickle.loads(state)
            g2 = c2.__await__()

            # Check that both the original and the copy yield the
            # remaining expected values.
            for j in range(i, len(expect)):
                assert next(g) == expect[j]
                assert next(g2) == expect[j]

    def test_coroutine_wrapper(self):
        c = durable_coroutine(1)
        g = c.__await__()
        assert next(g) == 1

        state = pickle.dumps((c, g))
        c2, g2 = pickle.loads(state)

        assert next(g2) == 2
        g3 = c2.__await__()
        assert next(g3) == 3

    def test_export_cr_fields(self):
        c = nested_coroutines(1)
        underlying = c.coroutine

        self.assertIsInstance(c.cr_frame, FrameType)
        self.assertIs(c.cr_frame, underlying.cr_frame)

        self.assertIsInstance(c.cr_code, CodeType)
        self.assertIs(c.cr_code, underlying.cr_code)

        def check():
            self.assertEqual(c.cr_running, underlying.cr_running)
            try:
                self.assertEqual(c.cr_suspended, underlying.cr_suspended)
            except AttributeError:
                pass
            self.assertEqual(c.cr_origin, underlying.cr_origin)
            self.assertIs(c.cr_await, underlying.cr_await)

        check()
        for _ in c.__await__():
            check()
        check()

    def test_name_conflict(self):
        @durable
        async def durable_coroutine():
            pass

        with self.assertRaises(ValueError):

            @durable
            async def durable_coroutine():
                pass

    def test_two_way(self):
        @durable
        async def two_way(a):
            x = await yields(a)
            a += 1
            y = await yields(a)
            a += 1
            z = await yields(a)
            return x + y + z

        input = 1
        sends = [10, 20, 30]
        expect_yields = [1, 2, 3]
        expect_output = 60

        c = two_way(1)
        g = c.__await__()

        actual_yields = []
        actual_return = None

        try:
            i = 0
            send = None
            while True:
                next_value = c.send(send)
                actual_yields.append(next_value)
                send = sends[i]
                i += 1
        except StopIteration as e:
            actual_return = e.value

        self.assertEqual(actual_yields, expect_yields)
        self.assertEqual(actual_return, expect_output)

    def test_throw(self):
        warnings.filterwarnings("ignore", category=DeprecationWarning)  # FIXME

        ok = False

        @durable
        async def check_throw():
            try:
                await yields(1)
            except RuntimeError:
                nonlocal ok
                ok = True

        c = check_throw()
        next(c.__await__())
        try:
            c.throw(RuntimeError)
        except StopIteration:
            pass
        self.assertTrue(ok)

    def test_close(self):
        ok = False

        @durable
        async def check_close():
            try:
                await yields(1)
            except GeneratorExit:
                nonlocal ok
                ok = True
                raise

        c = check_close()
        next(c.__await__())
        c.close()
        self.assertTrue(ok)
