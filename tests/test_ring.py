import unittest

import dispatch
import ring.task.v1.service_pb2
import dispatch.http.v1.http_pb2
import grpc
import google.protobuf.any_pb2

class TestRing(unittest.TestCase):
    def test_ring(self):
        channel = grpc.insecure_channel("localhost:4001")
        stub = ring.task.v1.service_pb2_grpc.ServiceStub(channel)


        request = dispatch.http.v1.http_pb2.Request(
                url="https://www.google.com",
                method="GET"
            )

        input = google.protobuf.any_pb2.Any()
        input.Pack(request)

        create_task_input = ring.task.v1.service_pb2.CreateTaskInput(
            coroutine_uri="arn:aws:lambda:us-west-2:012345678912:function:dispatch-http",
            input=input,
        )
        req = ring.task.v1.service_pb2.CreateTasksRequest(tasks=[create_task_input])
        resp = stub.CreateTasks(req)
