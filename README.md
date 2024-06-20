<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/dispatchrun/.github/blob/main/profile/dispatch_logo_dark.png?raw=true">
    <img alt="dispatch logo" src="https://github.com/dispatchrun/.github/blob/main/profile/dispatch_logo_light.png?raw=true" height="64">
  </picture>
</p>

# dispatch-py

[![Docs](https://github.com/dispatchrun/dispatch-py/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/dispatchrun/dispatch-py/actions/workflows/docs.yml)
[![PyPI](https://github.com/dispatchrun/dispatch-py/actions/workflows/pypi.yml/badge.svg?branch=main)](https://github.com/dispatchrun/dispatch-py/actions/workflows/pypi.yml)
[![Test](https://github.com/dispatchrun/dispatch-py/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/dispatchrun/dispatch-py/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/dispatch-py.svg)](https://badge.fury.io/py/dispatch-py)
[![Reference](https://img.shields.io/badge/API-Reference-lightblue.svg)](https://python.dispatch.run/main/reference/dispatch/)

Python package to develop applications with Dispatch.

[fastapi]: https://fastapi.tiangolo.com/tutorial/first-steps/
[pypi]: https://pypi.org/project/dispatch-py/
[signup]: https://console.dispatch.run/

- [What is Dispatch?](#what-is-dispatch)
- [Installation](#installation)
  - [Installing the Dispatch CLI](#installing-the-dispatch-cli)
  - [Installing the Dispatch SDK](#installing-the-dispatch-sdk)
- [Usage](#usage)
  - [Writing Dispatch Applications](#writing-dispatch-applications)
  - [Running Dispatch Applications](#running-dispatch-applications)
  - [Writing Transactional Applications with Dispatch](#writing-transactional-applications-with-dispatch)
  - [Integration with FastAPI](#integration-with-fastapi)
  - [Integration with Flask](#integration-with-flask)
  - [Configuration](#configuration)
  - [Serialization](#serialization)
- [Examples](#examples)
- [Contributing](#contributing)

## What is Dispatch?

Dispatch is a cloud service for developing scalable and reliable applications in
Python, including:

- **Event-Driven Architectures**
- **Background Jobs**
- **Transactional Workflows**
- **Multi-Tenant Data Pipelines**

Dispatch differs from alternative solutions by allowing developers to write
simple Python code: it has a **minimal API footprint**, which usually only
requires using a function decorator (no complex framework to learn), failure
recovery is built-in by default for transient errors like rate limits or
timeouts, with a **zero-configuration** model.

To get started, follow the instructions to [sign up for Dispatch][signup] 🚀.

## Installation

### Installing the Dispatch CLI

As a pre-requisite, we recommend installing the Dispatch CLI to simplify the
configuration and execution of applications that use Dispatch. On macOS, this
can be done easily using [Homebrew](https://docs.brew.sh/):

```console
brew tap dispatchrun/dispatch
brew install dispatch
```

Alternatively, you can download the latest `dispatch` binary from the
[Releases](https://github.com/dispatchrun/dispatch/releases) page.

_Note that this step is optional, applications that use Dispatch can run without
the CLI, passing configuration through environment variables or directly in the
code. However, the CLI automates the onboarding flow and simplifies the
configuration, so we recommend starting with it._

### Installing the Dispatch SDK

> :warning: The Dispatch SDK requires **Python 3.8** or higher.

The Python package is published on [PyPI][pypi] as **dispatch-py**, to install:

```console
pip install dispatch-py
```

> :bulb: The Python SDK has integrations with **FastAPI**, **Flask**,
> or the standard `http.server` package.
>
> For requests to integrate other frameworks, open an issue on [GitHub](https://github.com/dispatchrun/dispatch-py/issues/new

## Usage

### Writing Dispatch Applications

The following snippet shows how to write a very simple Dispatch application
that does the following:

1. declare a dispatch function named `greet` which can run asynchronously
2. schedule a call to `greet` with the argument `World`
3. run until all dispatched calls have completed

```python
# main.py
import dispatch

@dispatch.function
def greet(msg: str):
    print(f"Hello, ${msg}!")

dispatch.run(greet('World'))
```

Obviously, this is just an example, a real application would perform much more
interesting work, but it's a good start to get a sense of how to use Dispatch.

### Running Dispatch Applications

The simplest way to run a Dispatch application is to use the Dispatch CLI, first
we need to login:

```console
dispatch login
```

Then we are ready to run the example program we wrote above:

```console
dispatch run -- python3 main.py
```

### Writing Transactional Applications with Dispatch

The `@dispatch.function` decorator can also be applied to Python coroutines
(a.k.a. _async_ functions), in which case each `await` point becomes a
durability step in the execution. If the awaited operation fails, it is
automatically retried, and the parent function is paused until the result are
available or a permanent error is raised.

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
`gather` can be used to wait on multiple concurrent calls:

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

Dispatch converts Python coroutines to _Distributed Coroutines_, which can be
suspended and resumed on any instance of a service across a fleet. For a deep
dive on these concepts, read our blog post on
[_Distributed Coroutines with a Native Python Extension and Dispatch_](https://dispatch.run/blog/distributed-coroutines-in-python).

### Integration with FastAPI

Many web applications written in Python are developed using [FastAPI][fastapi].
Dispatch can integrate with these applications by instantiating a
`dispatch.fastapi.Dispatch` object. When doing so, the Dispatch functions
declared by the program can be invoked remotely over the same HTTP interface
used for the [FastAPI][fastapi] handlers.

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
`publish` function. The function runs concurrently to the rest of the
program, driven by the Dispatch SDK.

### Integration with Flask

Dispatch can also be integrated with web applications built on [Flask][flask].

The API is nearly identical to FastAPI above, instead use:

```python
from flask import Flask
from dispatch.flask import Dispatch

app = Flask(__name__)
dispatch = Dispatch(app)
```

[flask]: https://flask.palletsprojects.com/en/3.0.x/

### Configuration

The Dispatch CLI automatically configures the SDK, so manual configuration is
usually not required when running Dispatch applications. However, in some
advanced cases, it might be useful to explicitly set configuration options.

In order for Dispatch to interact with functions remotely, the SDK needs to be
configured with the address at which the server can be reached. The Dispatch
API Key must also be set, and optionally, a public signing key should be
configured to verify that requests originated from Dispatch. These
configuration options can be passed as arguments to the
the `Dispatch` constructor, but by default they will be loaded from environment
variables:

| Environment Variable        | Value Example                      |
| :-------------------------- | :--------------------------------- |
| `DISPATCH_API_KEY`          | `d4caSl21a5wdx5AxMjdaMeWehaIyXVnN` |
| `DISPATCH_ENDPOINT_URL`     | `https://service.domain.com`       |
| `DISPATCH_VERIFICATION_KEY` | `-----BEGIN PUBLIC KEY-----...`    |

### Serialization

Dispatch uses the [pickle][pickle] library to serialize coroutines.

[pickle]: https://docs.python.org/3/library/pickle.html

Serialization of coroutines is enabled by a CPython extension.

The user must ensure that the contents of their stack frames are
serializable. That is, users should avoid using variables inside
coroutines that cannot be pickled.

If a pickle error is encountered, serialization tracing can be enabled
with the `DISPATCH_TRACE=1` environment variable to debug the issue. The
stacks of coroutines and generators will be printed to stdout before
the pickle library attempts serialization.

For help with a serialization issues, please submit a [GitHub issue][issues].

[issues]: https://github.com/dispatchrun/dispatch-py/issues

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
