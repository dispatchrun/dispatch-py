import os
import unittest
from unittest import mock

from dispatch import Call, Client
from dispatch.proto import _any_unpickle as any_unpickle
from dispatch.test import DispatchServer, DispatchService, EndpointClient


class TestClient(unittest.TestCase):
    def setUp(self):
        endpoint_client = EndpointClient.from_url("http://function-service")

        api_key = "0000000000000000"
        self.dispatch_service = DispatchService(endpoint_client, api_key)
        self.dispatch_server = DispatchServer(self.dispatch_service)
        self.dispatch_client = Client(api_key, api_url=self.dispatch_server.url)

        self.dispatch_server.start()

    def tearDown(self):
        self.dispatch_server.stop()

    @mock.patch.dict(os.environ, {"DISPATCH_API_KEY": "WHATEVER"})
    def test_api_key_from_env(self):
        client = Client(api_url=self.dispatch_server.url)

        with self.assertRaisesRegex(
            PermissionError,
            r"Dispatch received an invalid authentication token \(check DISPATCH_API_KEY is correct\)",
        ) as mc:
            client.dispatch([Call(function="my-function", input=42)])

    def test_api_key_from_arg(self):
        client = Client(api_url=self.dispatch_server.url, api_key="WHATEVER")

        with self.assertRaisesRegex(
            PermissionError,
            r"Dispatch received an invalid authentication token \(check api_key is correct\)",
        ) as mc:
            client.dispatch([Call(function="my-function", input=42)])

    @mock.patch.dict(os.environ, {"DISPATCH_API_KEY": ""})
    def test_api_key_missing(self):
        with self.assertRaises(ValueError) as mc:
            Client()
        self.assertEqual(
            str(mc.exception),
            "missing API key: set it with the DISPATCH_API_KEY environment variable",
        )

    def test_url_bad_scheme(self):
        with self.assertRaises(ValueError) as mc:
            Client(api_url="ftp://example.com", api_key="foo")
        self.assertEqual(str(mc.exception), "Invalid API scheme: 'ftp'")

    def test_can_be_constructed_on_https(self):
        # Goal is to not raise an exception here. We don't have an HTTPS server
        # around to actually test this.
        Client(api_url="https://example.com", api_key="foo")

    def test_call_pickle(self):
        dispatch_ids = self.dispatch_client.dispatch(
            [Call(function="my-function", input=42)]
        )
        self.assertEqual(len(dispatch_ids), 1)

        pending_calls = self.dispatch_service.queue
        self.assertEqual(len(pending_calls), 1)
        dispatch_id, call, _ = pending_calls[0]
        self.assertEqual(dispatch_id, dispatch_ids[0])
        self.assertEqual(call.function, "my-function")
        self.assertEqual(any_unpickle(call.input), 42)

    def test_batch(self):
        batch = self.dispatch_client.batch()

        batch.add_call(Call(function="my-function", input=42)).add_call(
            Call(function="my-function", input=23)
        ).add_call(Call(function="my-function2", input=11))

        dispatch_ids = batch.dispatch()
        self.assertEqual(len(dispatch_ids), 3)

        pending_calls = self.dispatch_service.queue
        self.assertEqual(len(pending_calls), 3)
        dispatch_id0, call0, _ = pending_calls[0]
        dispatch_id1, call1, _ = pending_calls[1]
        dispatch_id2, call2, _ = pending_calls[2]
        self.assertListEqual(dispatch_ids, [dispatch_id0, dispatch_id1, dispatch_id2])
        self.assertEqual(call0.function, "my-function")
        self.assertEqual(any_unpickle(call0.input), 42)
        self.assertEqual(call1.function, "my-function")
        self.assertEqual(any_unpickle(call1.input), 23)
        self.assertEqual(call2.function, "my-function2")
        self.assertEqual(any_unpickle(call2.input), 11)

        self.assertEqual(len(batch.dispatch()), 0)  # batch was reset
