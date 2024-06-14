import pickle

from dispatch.function import Client, Registry
from dispatch.test import DISPATCH_API_KEY, DISPATCH_API_URL, DISPATCH_ENDPOINT_URL


def test_serializable():
    reg = Registry(
        name=__name__,
        endpoint=DISPATCH_ENDPOINT_URL,
        client=Client(
            api_key=DISPATCH_API_KEY,
            api_url=DISPATCH_API_URL,
        ),
    )

    @reg.function
    def my_function():
        pass

    s = pickle.dumps(my_function)
    pickle.loads(s)
    reg.close()
