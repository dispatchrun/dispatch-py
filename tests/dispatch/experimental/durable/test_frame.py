import unittest
from dataclasses import dataclass

from dispatch.experimental.durable import frame as ext


def generator(a):
    yield a
    a += 1
    yield a
    a += 1
    yield a


@dataclass
class Yields:
    n: int

    def __await__(self):
        yield self.n


async def coroutine(a):
    await Yields(a)
    a += 1
    await Yields(a)
    a += 1
    await Yields(a)


class TestFrame(unittest.TestCase):
    def test_generator_copy(self):
        # Create an instance and run it to the first yield point.
        g = generator(1)
        assert next(g) == 1

        # Copy the generator.
        g2 = generator(1)
        self.copy_to(g, g2)

        # The copy should start from where the previous generator was suspended.
        assert next(g2) == 2
        assert next(g2) == 3

        # Original generator is not affected.
        assert next(g) == 2
        assert next(g) == 3

    def test_coroutine_copy(self):
        # Create an instance and run it to the first yield point.
        c = coroutine(1)
        g = c.__await__()

        assert next(g) == 1

        # Copy the coroutine.
        c2 = coroutine(1)
        self.copy_to(c, c2)
        g2 = c2.__await__()

        # The copy should start from where the previous coroutine was suspended.
        assert next(g2) == 2
        assert next(g2) == 3

        # Original coroutine is not affected.
        assert next(g) == 2
        assert next(g) == 3

    def copy_to(self, from_obj, to_obj):
        ext.set_frame_state(to_obj, ext.get_frame_state(from_obj))
        ext.set_frame_ip(to_obj, ext.get_frame_ip(from_obj))
        ext.set_frame_sp(to_obj, ext.get_frame_sp(from_obj))
        for i in range(ext.get_frame_sp(from_obj)):
            is_null, obj = ext.get_frame_stack_at(from_obj, i)
            ext.set_frame_stack_at(to_obj, i, is_null, obj)
