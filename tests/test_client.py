import os
import unittest
from unittest import mock

import grpc
from google.protobuf import wrappers_pb2, any_pb2

from dispatch import Client, ExecutionInput, ExecutionID
from dispatch.coroutine import _any_unpickle as any_unpickle
from .task_service import ServerTest


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
            client.execute(
                [ExecutionInput(coroutine_uri="my-cool-coroutine", input=42)]
            )
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

    def test_create_one_execution_pickle(self):
        results = self.client.execute(
            [ExecutionInput(coroutine_uri="my-cool-coroutine", input=42)]
        )
        self.assertEqual(len(results), 1)
        id = results[0]

        created_tasks = self.servicer.created_tasks
        self.assertEqual(len(created_tasks), 1)
        entry = created_tasks[0]
        self.assertEqual(entry["id"], id)
        task = entry["task"]
        self.assertEqual(task.coroutine_uri, "my-cool-coroutine")
        self.assertEqual(any_unpickle(task.input), 42)

    def test_create_one_task_proto(self):
        proto = wrappers_pb2.Int32Value(value=42)
        results = self.client.execute(
            [ExecutionInput(coroutine_uri="my-cool-coroutine", input=proto)]
        )
        id = results[0]
        created_tasks = self.servicer.created_tasks
        entry = created_tasks[0]
        task = entry["task"]
        # proto has been wrapper in an any
        x = wrappers_pb2.Int32Value()
        task.input.Unpack(x)
        self.assertEqual(x, proto)

    def test_create_one_task_proto_any(self):
        proto = wrappers_pb2.Int32Value(value=42)
        proto_any = any_pb2.Any()
        proto_any.Pack(proto)
        results = self.client.execute(
            [ExecutionInput(coroutine_uri="my-cool-coroutine", input=proto_any)]
        )
        id = results[0]
        created_tasks = self.servicer.created_tasks
        entry = created_tasks[0]
        task = entry["task"]
        # proto any has not been modified
        self.assertEqual(task.input, proto_any)
