import pickle
import unittest
from types import coroutine

from dispatch.experimental.durable import durable


@coroutine
@durable
def yields(n):
    yield n


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
        self.skipTest("nested coroutines are not working")

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
