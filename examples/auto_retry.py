import random

import requests

import dispatch
import dispatch.integrations.requests

rng = random.Random(2)


def third_party_api_call(x):
    # Simulate a third-party API call that fails.
    print(f"Simulating third-party API call with {x}")
    if x < 3:
        print("RAISE EXCEPTION")
        raise requests.RequestException("Simulated failure")
    else:
        return "SUCCESS"


# Use the `dispatch.function` decorator to declare a stateful function.
@dispatch.function
def auto_retry():
    x = rng.randint(0, 5)
    return third_party_api_call(x)


if __name__ == "__main__":
    print(dispatch.run(auto_retry()))
