import unittest

import fastapi
from fastapi.testclient import TestClient

from dispatch import Client, TaskInput, TaskID
from dispatch.coroutine import Input, Output, Error, Status
from dispatch.coroutine import _any_unpickle as any_unpickle
import dispatch.fastapi
from .test_client import ServerTest
from . import executor_service


class TestFullFastapi(unittest.TestCase):
    def setUp(self):
        self.app = fastapi.FastAPI()
        dispatch.fastapi.configure(self.app, api_key="test-key")
        http_client = TestClient(self.app)
        self.app_client = executor_service.client(http_client)
        self.server = ServerTest()
        # shortcuts
        self.client = self.server.client
        self.servicer = self.server.servicer

    def tearDown(self):
        self.server.stop()

    def execute_tasks(self):
        self.server.execute(self.app_client)

    def test_simple_end_to_end(self):
        # The FastAPI server.
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value(f"Hello world: {input.input}")

        # The client.
        [task_id] = self.client.create_tasks(
            [TaskInput(coroutine_uri=my_cool_coroutine.uri, input=52)]
        )

        # Simulate execution for testing purposes.
        self.execute_tasks()

        # Validate results.
        resp = self.servicer.responses[task_id]
        self.assertEqual(any_unpickle(resp.exit.result.output), "Hello world: 52")

    def test_simple_call_with(self):
        @self.app.dispatch_coroutine()
        def my_cool_coroutine(input: Input) -> Output:
            return Output.value(f"Hello world: {input.input}")

        [task_id] = self.client.create_tasks([my_cool_coroutine.call_with(52)])
        self.execute_tasks()
        resp = self.servicer.responses[task_id]
        self.assertEqual(any_unpickle(resp.exit.result.output), "Hello world: 52")
