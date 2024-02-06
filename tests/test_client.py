import os
import unittest
from unittest import mock

import grpc
from google.protobuf import any_pb2, wrappers_pb2

from dispatch import Call, Client, DispatchID
from dispatch.function import _any_unpickle as any_unpickle

from .dispatch_service import ServerTest


class TestClient(unittest.TestCase):
    def setUp(self):
        self.server = ServerTest()
        # shortcuts
        self.servicer = self.server.servicer
        self.client = self.server.client

    def tearDown(self):
        self.server.stop()

    @mock.patch.dict(os.environ, {"DISPATCH_API_KEY": "WHATEVER"})
    def test_api_key_from_env(self):
        client = Client(api_url=f"http://127.0.0.1:{self.server.port}")

        with self.assertRaises(grpc._channel._InactiveRpcError) as mc:
            client.dispatch([Call(function="my-function", input=42)])
        self.assertTrue("got 'Bearer WHATEVER'" in str(mc.exception))

    def test_api_key_missing(self):
        with self.assertRaises(ValueError) as mc:
            client = Client()
        self.assertEqual(str(mc.exception), "api_key is required")

    def test_url_bad_scheme(self):
        with self.assertRaises(ValueError) as mc:
            client = Client(api_url="ftp://example.com", api_key="foo")
        self.assertEqual(str(mc.exception), "Invalid API scheme: 'ftp'")

    def test_can_be_constructed_on_https(self):
        # Goal is to not raise an exception here. We don't have an HTTPS server
        # around to actually test this.
        Client(api_url="https://example.com", api_key="foo")

    def test_call_pickle(self):
        results = self.client.dispatch([Call(function="my-function", input=42)])
        self.assertEqual(len(results), 1)
        id = results[0]

        dispatched_calls = self.servicer.dispatched_calls
        self.assertEqual(len(dispatched_calls), 1)
        entry = dispatched_calls[0]
        self.assertEqual(entry["dispatch_id"], id)
        call = entry["call"]
        self.assertEqual(call.function, "my-function")
        self.assertEqual(any_unpickle(call.input), 42)
