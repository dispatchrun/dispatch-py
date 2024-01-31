import unittest
import concurrent.futures.thread

import grpc

import ring.task.v1.service_pb2 as service_pb
import ring.task.v1.service_pb2_grpc as service_grpc
from dispatch import Client, TaskInput, TaskID
from dispatch.coroutine import _any_unpickle as any_unpickle


class FakeRing(service_grpc.ServiceServicer):
    def __init__(self):
        super().__init__()
        self.current_partition = 1
        self.current_block_id = 1
        self.current_offset = 0
        self.created_tasks = []

    def CreateTasks(self, request: service_pb.CreateTasksRequest, context):
        resp = service_pb.CreateTasksResponse()

        for t in request.tasks:
            id = TaskID(
                partition_number=self.current_partition,
                block_id=self.current_block_id,
                record_offset=self.current_offset,
                record_size=1,
            )
            self.current_offset += 1
            self.created_tasks.append({"id": id, "task": t})
            resp.tasks.append(service_pb.CreateTaskOutput(id=id._to_proto()))
        self.current_block_id += 1

        return resp


class TestClient(unittest.TestCase):
    def setUp(self):
        self.thread_pool = concurrent.futures.thread.ThreadPoolExecutor()
        self.server = grpc.server(self.thread_pool)

        port = self.server.add_insecure_port("127.0.0.1:0")

        self.servicer = FakeRing()

        service_grpc.add_ServiceServicer_to_server(self.servicer, self.server)
        self.server.start()

        self.client = Client(api_key="test", api_url=f"http://127.0.0.1:{port}")

    def tearDown(self):
        self.server.stop(0)
        self.server.wait_for_termination()
        self.thread_pool.shutdown(wait=True, cancel_futures=True)

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
