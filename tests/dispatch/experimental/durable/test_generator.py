import pickle
import unittest

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
