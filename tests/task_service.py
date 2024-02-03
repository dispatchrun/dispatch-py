import concurrent.futures.thread

import grpc

import dispatch.sdk.v1.endpoint_pb2 as endpoint_pb
import dispatch.sdk.v1.endpoint_pb2_grpc as endpoint_grpc
import dispatch.sdk.v1.executor_pb2 as executor_pb
import dispatch.sdk.v1.executor_pb2_grpc as executor_grpc
from dispatch import Client, ExecutionID, ExecutionInput

_test_auth_token = "THIS_IS_A_TEST_AUTH_TOKEN"


class FakeEndpointService(endpoint_grpc.EndpointServiceServicer):
    def __init__(self):
        super().__init__()
        self.current_partition = 1
        self.current_block_id = 1
        self.current_offset = 0

        self.created_tasks = []
        self.responses = {}  # indexed by task id

        self.pending_tasks = []

    def _make_task_id(self) -> ExecutionID:
        parts = [
            self.current_partition,
            self.current_block_id,
            self.current_offset,
            1,  # record_size
        ]
        return "".join("{:08x}".format(a) for a in parts)

    def _validate_authentication(self, context: grpc.ServicerContext):
        expected = f"Bearer {_test_auth_token}"
        for key, value in context.invocation_metadata():
            if key == "authorization":
                if value == expected:
                    return
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    f"Invalid authorization header. Expected '{expected}', got {value!r}",
                )
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization header")

    def CreateExecutions(self, request: endpoint_pb.CreateExecutionsRequest, context):
        self._validate_authentication(context)

        resp = endpoint_pb.CreateExecutionsResponse()

        for t in request.executions:
            id = self._make_task_id()
            self.current_offset += 1
            self.created_tasks.append({"id": id, "task": t})
            self.pending_tasks.append({"id": id, "task": t})
            resp.ids.append(id)
        self.current_block_id += 1

        return resp

    def execute(self, client: executor_grpc.ExecutorServiceStub):
        """Synchronously execute all the pending tasks until there is no
        pending task left.

        """
        while len(self.pending_tasks) > 0:
            entry = self.pending_tasks.pop(0)
            task = entry["task"]

            req = executor_pb.ExecuteRequest(
                coroutine_uri=task.coroutine_uri, input=task.input
            )

            resp = client.Execute(req)
            self.responses[entry["id"]] = resp


class ServerTest:
    """Server test is a test fixture that starts a fake task service server and
    provides a client setup to talk to it.

    Instantiate in a setUp() method and call stop() in a tearDown() method.

    """

    def __init__(self):
        self.thread_pool = concurrent.futures.thread.ThreadPoolExecutor()
        self.server = grpc.server(self.thread_pool)

        self.port = self.server.add_insecure_port("127.0.0.1:0")

        self.servicer = FakeEndpointService()

        endpoint_grpc.add_EndpointServiceServicer_to_server(self.servicer, self.server)
        self.server.start()

        self.client = Client(
            api_key=_test_auth_token, api_url=f"http://127.0.0.1:{self.port}"
        )

    def stop(self):
        self.server.stop(0)
        self.server.wait_for_termination()
        self.thread_pool.shutdown(wait=True, cancel_futures=True)

    def execute(self, client: executor_grpc.ExecutorServiceStub):
        return self.servicer.execute(client)
