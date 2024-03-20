import requests
import uvicorn
from fastapi import FastAPI

from dispatch.fastapi import Dispatch

# Create the FastAPI app like you normally would.
app = FastAPI()

# Create a Dispatch instance and pass the FastAPI app to it. It automatically
# sets up the necessary routes and handlers.
dispatch = Dispatch(app)


# Use the `dispatch.function` decorator declare a stateful function.
@dispatch.function
def publish(url, payload):
    r = requests.post(url, data=payload)
    r.raise_for_status()


# This is a normal FastAPI route that handles regular traffic.
@app.get("/")
def root():
    # Use the `dispatch` method to call the stateful function. This call is
    # returns immediately after scheduling the function call, which happens in
    # the background.
    publish.dispatch("https://httpstat.us/200", {"hello": "world"})
    # Sending a response now that the HTTP handler has completed.
    return "OK"


if __name__ == "__main__":
    dispatch.run()
