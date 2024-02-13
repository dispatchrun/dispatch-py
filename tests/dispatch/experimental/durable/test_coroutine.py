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
