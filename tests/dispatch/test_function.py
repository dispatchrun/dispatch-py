import pickle
import unittest

from dispatch.remote import Endpoint


class TestFunction(unittest.TestCase):
    def setUp(self):
        self.dispatch = Endpoint(
            endpoint="http://example.com",
            api_url="http://dispatch.com",
            api_key="foobar",
        )

    def test_serializable(self):
        @self.dispatch.function
        def my_function():
            pass

        s = pickle.dumps(my_function)
        pickle.loads(s)
