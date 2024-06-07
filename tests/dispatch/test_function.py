import pickle

from dispatch.test import Registry


def test_serializable():
    reg = Registry()

    @reg.function
    def my_function():
        pass

    s = pickle.dumps(my_function)
    pickle.loads(s)
