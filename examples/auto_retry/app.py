"""Auto-retry example.

This example demonstrates how stateful functions automatically retry on failure.

Make sure to follow the setup instructions at
https://docs.stealthrocket.cloud/dispatch/stateful-functions/getting-started/

Run with:

uvicorn app:app

curl http://localhost:8000/


Observe the logs in the terminal where the server is running. It will show a
handful of attempts before succeeding.

"""

import random

import requests
from fastapi import FastAPI

from dispatch.fastapi import Dispatch

# Create the FastAPI app like you normally would.
app = FastAPI()

# chosen by fair dice roll. guaranteed to be random.
rng = random.Random(2)

# Create a Dispatch instance and pass the FastAPI app to it. It automatically
# sets up the necessary routes and handlers.
dispatch = Dispatch(app)


def third_party_api_call(x):
    # Simulate a third-party API call that fails.
    print(f"Simulating third-party API call with {x}")
    if x < 3:
        raise requests.RequestException("Simulated failure")
    else:
        return "SUCCESS"


# Use the `dispatch.function` decorator to declare a stateful function.
@dispatch.function
def some_logic():
    print("Executing some logic")
    x = rng.randint(0, 5)
    result = third_party_api_call(x)
    print("RESULT:", result)


# This is a normal FastAPI route that handles regular traffic.
@app.get("/")
def root():
    # Use the `dispatch` method to call the stateful function. This call is
    # returns immediately after scheduling the function call, which happens in
    # the background.
    some_logic.dispatch()
    # Sending a response now that the HTTP handler has completed.
    return "OK"
