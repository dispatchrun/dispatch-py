import unittest
import concurrent.futures.thread

import dispatch
import ring.task.v1.service_pb2 as service_pb
import ring.task.v1.service_pb2_grpc as service_grpc
import dispatch.http.v1.http_pb2
import grpc
import google.protobuf.any_pb2


class FakeRing(service_grpc.ServiceServicer):
    def CreateTasks(self, request, context):
        return service_pb.CreateTasksResponse()


class TestRing(unittest.TestCase):
    def setUp(self):
        self.thread_pool = concurrent.futures.thread.ThreadPoolExecutor()
        self.server = grpc.server(self.thread_pool)

        port = self.server.add_insecure_port("127.0.0.1:0")

        servicer = FakeRing()

        service_grpc.add_ServiceServicer_to_server(servicer, self.server)
        self.server.start()

        channel = grpc.insecure_channel(f"127.0.0.1:{port}")
        self.ring_stub = service_grpc.ServiceStub(channel)

    def tearDown(self):
        self.server.stop(0)
        self.server.wait_for_termination()
        self.thread_pool.shutdown(wait=True, cancel_futures=True)

    def test_ring(self):

        request = dispatch.http.v1.http_pb2.Request(
            url="https://www.google.com", method="GET"
        )

        input = google.protobuf.any_pb2.Any()
        input.Pack(request)

        create_task_input = service_pb.CreateTaskInput(
            coroutine_uri="arn:aws:lambda:us-west-2:012345678912:function:dispatch-http",
            input=input,
        )
        req = service_pb.CreateTasksRequest(tasks=[create_task_input])
        resp = self.ring_stub.CreateTasks(req)
