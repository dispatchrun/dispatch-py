[![Docs](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/docs.yml/badge.svg?branch=)](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/docs.yml)
[![PyPI](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/pypi.yml/badge.svg?branch=)](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/pypi.yml)
[![Test](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/test.yml/badge.svg?branch=)](https://github.com/stealthrocket/dispatch-sdk-python/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/dispatch-functions.svg)](https://badge.fury.io/py/dispatch-functions)
[![Reference](https://img.shields.io/badge/API-Reference-lightblue.svg)](https://python.stealthrocket.cloud/main/reference/dispatch/)
<img align="right" src="https://github.com/stealthrocket/dispatch-sdk-protobuf/assets/865510/87162355-e184-4058-a733-650eee53f333" width="200"/>

# Dispatch SDK for Python

This package implements the Dispatch SDK for Python.

[fastapi]: https://fastapi.tiangolo.com/tutorial/first-steps/
[ngrok]:   https://ngrok.com/
[pypi]:    https://pypi.org/project/dispatch-functions/
[signup]:  https://docs.stealthrocket.cloud/stateful-functions/getting-started

- [What is Dispatch?](#what-is-dispatch)
- [Installation](#installation)
- [Usage](#usage)
  - [Configuration](#configuration)
  - [Integration with FastAPI](#integration-with-fastapi)
  - [Local testing with ngrok](#local-testing-with-ngrok)
  - [Durable coroutines for Python](#durable-coroutines-for-python)
- [Examples](#examples)
- [Contributing](#contributing)

## What is Dispatch?

Dispatch is a platform for developing reliable distributed systems. Dispatch
provides a simple programming model based on durable coroutines to manage the
scheduling of function calls across a fleet of service instances. Orchestration
of function calls is managed by Dispatch, providing **fair scheduling**,
transparent **retry of failed operations**, and **durability**.

To get started, follow the instructions to [sign up for Dispatch][signup] 🚀.

## Installation

This package is published on [PyPI][pypi] as **dispatch-functions**, to install:
```sh
pip install dispatch-functions
```

## Usage

The SDK allows Python applications to declare *Stateful Functions* that the
Dispatch scheduler can orchestrate. This is the bare minimum structure used
to declare stateful functions:
```python
@dispatch.function
def action(msg):
    ...
```
The **@dispatch.function** decorator declares a function that can be run by
the Dispatch scheduler. The call has durable execution semantics; if the
function fails with a temporary error, it is automatically retried, even if
the program is restarted, or if multiple instances are deployed.

In this example, the decorator adds a method to the `action` object, allowing
the program to dispatch an asynchronous invocation of the function; for example:
```python
action.dispatch('hello')
```

### Configuration

To interact with stateful functions, the SDK needs to be configured with the
address at which the server can be reached. The Dispatch API Key must also be
set, and optionally, a public signing key should be configured to verify that
requests received by the stateful functions originated from the Dispatch
scheduler. These configuration options can be passed as arguments to the
the `Dispatch` constructor, but by default they will be loaded from environment
variables:

| Environment Variable        | Value Example                      |
| :-------------------------- | :--------------------------------- |
| `DISPATCH_API_KEY`          | `d4caSl21a5wdx5AxMjdaMeWehaIyXVnN` |
| `DISPATCH_ENDPOINT_URL`     | `https://service.domain.com`       |
| `DISPATCH_VERIFICATION_KEY` | `-----BEGIN PUBLIC KEY-----...`    |

Finally, the `Dispatch` instance needs to mount a route on a HTTP server in to
receive requests from the scheduler. At this time, the SDK integrates with
FastAPI; adapters for other popular Python frameworks will be added in the
future.

### Integration with FastAPI

The following code snippet is a complete example showing how to install a
`Dispatch` instance on a [FastAPI][fastapi] server:

```python
from fastapi import FastAPI
from dispatch.fastapi import Dispatch
import requests

app = FastAPI()
dispatch = Dispatch(app)

@dispatch.function
def publish(url, payload):
    r = requests.post(url, data=payload)
    r.raise_for_status()

@app.get('/')
def root():
    publish.dispatch('https://httpstat.us/200', {'hello': 'world'})
    return {'answer': 42}
```

In this example, GET requests on the HTTP server dispatch calls to the
`publish` stateful function. The function runs concurrently to the rest of the
program, driven by the Dispatch scheduler.

The instantiation of the `Dispatch` object on the `FastAPI` application
automatically installs the HTTP route needed for the scheduler to run stateful
functions.

### Local testing with ngrok

To enable local testing, a common approach consists of using [ngrok][ngrok] to
setup a public endpoint that forwards to the server running on localhost.

For example, assuming the server is running on port 8000 (which is the default
with FastAPI), the command to create a ngrok tunnel is:
```sh
ngrok http http://localhost:8000
```
Running this command opens a terminal interface that looks like this:
```
ngrok

Build better APIs with ngrok. Early access: ngrok.com/early-access

Session Status                online
Account                       Alice (Plan: Free)
Version                       3.6.0
Region                        United States (California) (us-cal-1)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://f441-2600-1700-2802-e01f-6861-dbc9-d551-ecfb.ngrok-free.app -> http://localhost:8000
```
To configure the Dispatch SDK, set the endpoint URL to the endpoint for the
**Forwarding** parameter; each ngrok instance is unique, so you would have a
different value, but in this example it would be:
```sh
export DISPATCH_ENDPOINT_URL="https://f441-2600-1700-2802-e01f-6861-dbc9-d551-ecfb.ngrok-free.app"
```

### Durable coroutines for Python

The `@dispatch.function` decorator can also be applied to Python coroutines
(a.k.a. *async* functions), in which case each await point on another
stateful function becomes a durability step in the execution: if the awaited
operation fails, it is automatically retried and the parent function is paused
until the result becomes available, or a permanent error is raised.

```python
@dispatch.function
async def pipeline(msg):
    # Each await point is a durability step, the functions can be run across the
    # fleet of service instances and retried as needed without losing track of
    # progress through the function execution.
    msg = await transform1(msg)
    msg = await transform2(msg)
    await publish(msg)

@dispatch.function
async def publish(msg):
    # Each dispatch function runs concurrently to the others, even if it does
    # blocking operations like this POST request, it does not prevent other
    # concurrent operations from carrying on in the program.
    r = requests.post("https://somewhere.com/", data=msg)
    r.raise_for_status()

@dispatch.function
async def transform1(msg):
    ...

@dispatch.function
async def transform2(msg):
    ...
```

This model is composable and can be used to create fan-out/fan-in control flows.
`gather` can be used to wait on multiple concurrent calls to stateful functions,
for example:

```python
from dispatch import gather

@dispatch.function
async def process(msgs):
    concurrent_calls = [transform(msg) for msg in msgs]
    return await gather(*concurrent_calls)

@dispatch.function
async def transform(msg):
    ...
```

## Examples

Check out the [examples](examples/) directory for code samples to help you get
started with the SDK.

## Contributing

Contributions are always welcome! Would you spot a typo or anything that needs
to be improved, feel free to send a pull request.

Pull requests need to pass all CI checks before getting merged. Anything that
isn't a straightforward change would benefit from being discussed in an issue
before submitting a change.

Remember to be respectful and open minded!
