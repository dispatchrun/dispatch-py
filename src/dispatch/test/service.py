import os
import threading
from collections import OrderedDict
from typing import TypeAlias

import grpc

import dispatch.sdk.v1.call_pb2 as call_pb
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
import dispatch.sdk.v1.function_pb2 as function_pb
from dispatch.id import DispatchID
from dispatch.proto import Status
from dispatch.test import EndpointClient

_default_retry_on_status = {
    Status.THROTTLED,
    Status.TIMEOUT,
    Status.TEMPORARY_ERROR,
    Status.DNS_ERROR,
    Status.TCP_ERROR,
    Status.TLS_ERROR,
    Status.HTTP_ERROR,
}


RoundTrip: TypeAlias = tuple[function_pb.RunRequest, function_pb.RunResponse]
"""A request to a Dispatch endpoint, and the response that was received."""


class DispatchService(dispatch_grpc.DispatchServiceServicer):
    """Test instance of Dispatch that provides the bare minimum
    functionality required to test functions locally."""

    def __init__(
        self,
        endpoint_client: EndpointClient,
        api_key: str | None = None,
        retry_on_status: set[Status] | None = None,
        collect_roundtrips: bool = False,
    ):
        """Initialize the Dispatch service.

        Args:
            endpoint_client: Client to use to interact with the local Dispatch
                endpoint (that provides the functions).
            api_key: Expected API key on requests to the service. If omitted, the
                value of the DISPATCH_API_KEY environment variable is used instead.
            retry_on_status: Set of status codes to enable retries for.
            collect_roundtrips: Enable collection of request/response round-trips
                to the configured endpoint.
        """
        super().__init__()

        self.endpoint_client = endpoint_client

        if api_key is None:
            api_key = os.getenv("DISPATCH_API_KEY")
        self.api_key = api_key

        if retry_on_status is None:
            retry_on_status = _default_retry_on_status
        self.retry_on_status = retry_on_status

        self._next_dispatch_id = 1

        self.queue: list[tuple[DispatchID, call_pb.Call]] = []

        self.roundtrips: OrderedDict[DispatchID, list[RoundTrip]] | None = None
        if collect_roundtrips:
            self.roundtrips = OrderedDict()

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._work_signal = threading.Condition()

    def Dispatch(self, request: dispatch_pb.DispatchRequest, context):
        """RPC handler for Dispatch requests. Requests are only queued for
        processing here."""
        self._validate_authentication(context)

        resp = dispatch_pb.DispatchResponse()

        with self._work_signal:
            for call in request.calls:
                dispatch_id = self._make_dispatch_id()
                resp.dispatch_ids.append(dispatch_id)
                self.queue.append((dispatch_id, call))

            self._work_signal.notify()

        return resp

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

    def _make_dispatch_id(self) -> DispatchID:
        dispatch_id = self._next_dispatch_id
        self._next_dispatch_id += 1
        return "{:032x}".format(dispatch_id)

    def dispatch_calls(self):
        """Synchronously dispatch pending function calls to the
        configured endpoint."""
        _next_queue = []
        while self.queue:
            dispatch_id, call = self.queue.pop(0)

            request = function_pb.RunRequest(
                function=call.function,
                input=call.input,
            )

            response = self.endpoint_client.run(request)

            if self.roundtrips is not None:
                try:
                    roundtrips = self.roundtrips[dispatch_id]
                except KeyError:
                    roundtrips = []

                roundtrips.append((request, response))
                self.roundtrips[dispatch_id] = roundtrips

            if Status(response.status) in self.retry_on_status:
                _next_queue.append((dispatch_id, call))

            elif response.HasField("poll"):
                # TODO: register pollers so that the service can deliver call results once ready
                for call in response.poll.calls:
                    dispatch_id = self._make_dispatch_id()
                    _next_queue.append((dispatch_id, call))

        self.queue = _next_queue

    def start(self):
        """Start starts a background thread to continuously dispatch calls to the
        configured endpoint."""
        if self._thread is not None:
            raise RuntimeError("service has already been started")

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._dispatch_continuously)
        self._thread.start()

    def stop(self):
        """Stop stops the background thread that's dispatching calls to
        the configured endpoint."""
        self._stop_event.set()
        with self._work_signal:
            self._work_signal.notify()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def _dispatch_continuously(self):
        while True:
            with self._work_signal:
                if not self.queue and not self._stop_event.is_set():
                    self._work_signal.wait()

            if self._stop_event.is_set():
                break

            self.dispatch_calls()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
