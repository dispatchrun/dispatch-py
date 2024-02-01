import unittest

from google.protobuf import wrappers_pb2, any_pb2

from dispatch import Client, TaskInput, TaskID
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

    def test_authentication(self): ...

    def test_create_one_task_pickle(self):
        results = self.client.create_tasks(
            [TaskInput(coroutine_uri="my-cool-coroutine", input=42)]
        )
        self.assertEqual(len(results), 1)
        id = results[0]
        self.assertTrue(id.partition_number != 0)
        self.assertTrue(id.block_id != 0)

        created_tasks = self.servicer.created_tasks
        self.assertEqual(len(created_tasks), 1)
        entry = created_tasks[0]
        self.assertEqual(entry["id"], id)
        task = entry["task"]
        self.assertEqual(task.coroutine_uri, "my-cool-coroutine")
        self.assertEqual(any_unpickle(task.input), 42)

    def test_create_one_task_proto(self):
        proto = wrappers_pb2.Int32Value(value=42)
        results = self.client.create_tasks(
            [TaskInput(coroutine_uri="my-cool-coroutine", input=proto)]
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
        results = self.client.create_tasks(
            [TaskInput(coroutine_uri="my-cool-coroutine", input=proto)]
        )
        id = results[0]
        created_tasks = self.servicer.created_tasks
        entry = created_tasks[0]
        task = entry["task"]
        # proto any has not been modified
        self.assertEqual(task.input, proto_any)
