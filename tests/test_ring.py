import unittest

import dispatch
import ring.task.v1.service_pb2
import grpc


class TestRing(unittest.TestCase):
    def test_ring(self):
        channel = grpc.insecure_channel('localhost:4001')
        stub = ring.task.v1.service_pb2_grpc.ServiceStub(channel)
        create_task_input = ring.task.v1.service_pb2.CreateTaskInput(
            coroutine_uri = "dispatch-http",
            input = ring.http.v1.service_pb2.HttpInput(
                url = "https://www.google.com",
                method = "GET",
                headers = {
                    "Accept": "text/html",
                    "User-Agent": "dispatch"
                }
            )
        )
        req = ring.task.v1.service_pb2.CreateTasksRequest(tasks=[create_task_input])
        resp = stub.CreateTasks(req)
