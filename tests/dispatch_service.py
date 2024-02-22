import os
from collections import OrderedDict

import grpc

import dispatch.sdk.v1.call_pb2 as call_pb
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
import dispatch.sdk.v1.function_pb2 as function_pb
import dispatch.sdk.v1.status_pb2 as status_pb
from dispatch import DispatchID
from dispatch.test import EndpointClient


class MockDispatchService(dispatch_grpc.DispatchServiceServicer):
    def __init__(self, endpoint_client: EndpointClient, api_key: str | None = None):
        super().__init__()

        self.endpoint_client = endpoint_client

        if api_key is None:
            api_key = os.getenv("DISPATCH_API_KEY")
        self.api_key = api_key

        self._next_dispatch_id = 1

        self.pending_calls: list[tuple[DispatchID, call_pb.Call]] = []
        self.responses: OrderedDict[DispatchID, function_pb.RunResponse] = OrderedDict()

    def _make_dispatch_id(self) -> DispatchID:
        dispatch_id = self._next_dispatch_id
        self._next_dispatch_id += 1
        return "{:032x}".format(dispatch_id)

    def _validate_authentication(self, context: grpc.ServicerContext):
        expected = f"Bearer {self.api_key}"
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
            self.pending_calls.append((dispatch_id, call))
            resp.dispatch_ids.append(dispatch_id)

        return resp

    def dispatch_calls(self):
        """Synchronously dispatch all pending function calls."""

        _next_pending_calls = []

        while self.pending_calls:
            dispatch_id, call = self.pending_calls.pop(0)

            req = function_pb.RunRequest(
                function=call.function,
                input=call.input,
            )

            resp = self.endpoint_client.run(req)
            self.responses[dispatch_id] = resp

            if self._should_retry_status(resp.status):
                dispatch_id = self._make_dispatch_id()
                _next_pending_calls.append((dispatch_id, call))

        self.pending_calls = _next_pending_calls

    def _should_retry_status(self, status: status_pb.Status) -> bool:
        match status:
            case (
                status_pb.STATUS_THROTTLED
                | status_pb.STATUS_TIMEOUT
                | status_pb.STATUS_TEMPORARY_ERROR
                | status_pb.STATUS_INCOMPATIBLE_STATE
                | status_pb.STATUS_DNS_ERROR
                | status_pb.STATUS_TCP_ERROR
                | status_pb.STATUS_TLS_ERROR
                | status_pb.STATUS_HTTP_ERROR
            ):
                return True
            case _:
                return False
