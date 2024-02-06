import concurrent.futures.thread

import grpc

import dispatch.sdk.v1.call_pb2 as call_pb
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
import dispatch.sdk.v1.function_pb2 as function_pb
import dispatch.sdk.v1.function_pb2_grpc as function_grpc
from dispatch import Client, DispatchID

_test_auth_token = "THIS_IS_A_TEST_AUTH_TOKEN"


class FakeDispatchService(dispatch_grpc.DispatchServiceServicer):
    def __init__(self):
        super().__init__()
        self._next_dispatch_id = 1
        self._pending_calls = []

        self.responses = {}  # indexed by dispatch ID
        self.dispatched_calls = []

    def _make_dispatch_id(self) -> DispatchID:
        dispatch_id = self._next_dispatch_id
        self._next_dispatch_id += 1
        return "{:032x}".format(dispatch_id)

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

    def Dispatch(self, request: dispatch_pb.DispatchRequest, context):
        self._validate_authentication(context)

        resp = dispatch_pb.DispatchResponse()

        for call in request.calls:
            dispatch_id = self._make_dispatch_id()
            self.dispatched_calls.append({"dispatch_id": dispatch_id, "call": call})
            self._pending_calls.append({"dispatch_id": dispatch_id, "call": call})
            resp.dispatch_ids.append(dispatch_id)

        return resp

    def execute(self, client: function_grpc.FunctionServiceStub):
        """Synchronously execute all pending function calls."""
        while len(self._pending_calls) > 0:
            entry = self._pending_calls.pop(0)
            call: call_pb.Call = entry["call"]

            req = function_pb.RunRequest(
                function=call.function,
                input=call.input,
            )

            resp = client.Run(req)
            self.responses[entry["dispatch_id"]] = resp


class ServerTest:
    """Server test is a test fixture that starts a fake dispatch server and
    provides a client setup to talk to it.

    Instantiate in a setUp() method and call stop() in a tearDown() method.
    """

    def __init__(self):
        self.thread_pool = concurrent.futures.thread.ThreadPoolExecutor()
        self.server = grpc.server(self.thread_pool)

        self.port = self.server.add_insecure_port("127.0.0.1:0")

        self.servicer = FakeDispatchService()

        dispatch_grpc.add_DispatchServiceServicer_to_server(self.servicer, self.server)
        self.server.start()

        self.client = Client(
            api_key=_test_auth_token, api_url=f"http://127.0.0.1:{self.port}"
        )

    def stop(self):
        self.server.stop(0)
        self.server.wait_for_termination()
        self.thread_pool.shutdown(wait=True, cancel_futures=True)

    def execute(self, client: function_grpc.FunctionServiceStub):
        return self.servicer.execute(client)
