"""Getting started example.

This is the most basic example to get started with Dispatch Functions.

Follow along with the tutorial at:
https://docs.dispatch.run/dispatch/stateful-functions/getting-started/

The program starts a FastAPI server and initializes the Dispatch SDK that
registers one function. This function makes a dummy but durable HTTP request.
The server exposes one route (`/`). This route's handler asynchronously invokes
the durable function.

# Setup

## Get a Dispatch API key

Sign up for Dispatch and generate a new API key:
https://docs.dispatch.run/stateful-functions/getting-started#creating-an-api-key

## Create a local tunnel

Use ngrok to create a local tunnel to your server.

1. Download and install ngrok from https://ngrok.com/download
2. Start a new tunnel with `ngrok http http://localhost:8000`

Note the forwarding address.

## Install dependencies

pip install dispatch-py[fastapi] requests uvicorn[standard]

# Launch the example

1. Export the environment variables for the public address and the dispatch API
   key. For example:

export DISPATCH_ENDPOINT_URL=https://ab642fb8661e.ngrok.app
export DISPATCH_API_KEY=s56kfDPal9ErVvVxgFGL6YTcLOvchtg5
export "DISPATCH_VERIFICATION_KEY=`curl -s \
    -d '{}' \
    -H "Authorization: Bearer $DISPATCH_API_KEY" \
    -H "Content-Type: application/json" \
    https://api.dispatch.run/dispatch.v1.SigningKeyService/CreateSigningKey | \
        jq -r .key.asymmetricKey.publicKey`"

2. Start the server:

uvicorn app:app

3. Request the root handler:

curl http://localhost:8000/

"""

import requests
from fastapi import FastAPI

from dispatch.fastapi import Endpoint

# Create the FastAPI app like you normally would.
app = FastAPI()

# Create a Dispatch instance and pass the FastAPI app to it. It automatically
# sets up the necessary routes and handlers.
dispatch = Endpoint(app)


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
