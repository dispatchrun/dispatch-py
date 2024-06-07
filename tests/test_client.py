import os
from unittest import mock

import pytest

import dispatch.test
from dispatch import Call
from dispatch.test import Client


def server() -> dispatch.test.Server:
    return dispatch.test.Server(dispatch.test.Service())


@mock.patch.dict(os.environ, {"DISPATCH_API_KEY": ""})
def test_api_key_missing():
    with pytest.raises(ValueError) as mc:
        Client()
    assert (
        str(mc.value)
        == "missing API key: set it with the DISPATCH_API_KEY environment variable"
    )


def test_url_bad_scheme():
    with pytest.raises(ValueError) as mc:
        Client(api_url="ftp://example.com", api_key="foo")
    assert str(mc.value) == "Invalid API scheme: 'ftp'"


def test_can_be_constructed_on_https():
    # Goal is to not raise an exception here. We don't have an HTTPS server
    # around to actually test this.
    Client(api_url="https://example.com", api_key="foo")


@mock.patch.dict(os.environ, {"DISPATCH_API_KEY": "0000000000000000"})
@pytest.mark.asyncio
async def test_api_key_from_env():
    async with server() as api:
        client = Client(api_url=api.url)

        with pytest.raises(
            PermissionError,
            match=r"Dispatch received an invalid authentication token \(check DISPATCH_API_KEY is correct\)",
        ) as mc:
            await client.dispatch([Call(function="my-function", input=42)])


@pytest.mark.asyncio
async def test_api_key_from_arg():
    async with server() as api:
        client = Client(api_url=api.url, api_key="WHATEVER")

        with pytest.raises(
            PermissionError,
            match=r"Dispatch received an invalid authentication token \(check api_key is correct\)",
        ) as mc:
            await client.dispatch([Call(function="my-function", input=42)])
