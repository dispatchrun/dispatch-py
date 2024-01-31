import unittest

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
