import unittest
from dispatch.experimental.durable import _frame as ext


def generator(a):
    yield a
    a += 1
    yield a
    a += 1
    yield a


class TestFrame(unittest.TestCase):
    def test_copy(self):
        # Create an instance and run it to the first yield point.
        g = generator(1)
        assert next(g) == 1

        # Copy the generator.
        g2 = generator(1)
        ext.set_generator_frame_state(g2, ext.get_generator_frame_state(g))
        ext.set_frame_ip(g2, ext.get_frame_ip(g))
        ext.set_frame_sp(g2, ext.get_frame_sp(g))
        for i in range(ext.get_frame_sp(g)):
            is_null, obj = ext.get_frame_stack_at(g, i)
            ext.set_frame_stack_at(g2, i, is_null, obj)

        # The copy should start from where the previous generator was suspended.
        assert next(g2) == 2
        assert next(g2) == 3

        # Original generator is not affected.
        assert next(g) == 2
        assert next(g) == 3
