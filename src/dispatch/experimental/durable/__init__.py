"""A decorator that makes generators and coroutines serializable.

This module defines a @durable decorator that can be applied to generator
functions and async functions. The generator and coroutine instances
they create can be pickled.

Example usage:

    import pickle
    from dispatch.experimental.durable import durable

    @durable
    def my_generator():
        for i in range(3):
            yield i

    # Run the generator to its first yield point:
    g = my_generator()
    print(next(g))  # 0

    # Make a copy, and consume the remaining items:
    b = pickle.dumps(g)
    g2 = pickle.loads(b)
    print(next(g2))  # 1
    print(next(g2))  # 2

    # The original is not affected:
    print(next(g))  # 1
    print(next(g))  # 2
"""

from .function import durable

__all__ = ["durable"]
