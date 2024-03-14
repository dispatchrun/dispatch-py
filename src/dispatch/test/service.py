import enum
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypeAlias

import grpc
import httpx

import dispatch.sdk.v1.call_pb2 as call_pb
import dispatch.sdk.v1.dispatch_pb2 as dispatch_pb
import dispatch.sdk.v1.dispatch_pb2_grpc as dispatch_grpc
import dispatch.sdk.v1.function_pb2 as function_pb
import dispatch.sdk.v1.poll_pb2 as poll_pb
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


logger = logging.getLogger(__name__)


RoundTrip: TypeAlias = tuple[function_pb.RunRequest, function_pb.RunResponse]
"""A request to a Dispatch endpoint, and the response that was received."""


class CallType(enum.Enum):
    """Type of function call."""

    CALL = 0
    RESUME = 1
    RETRY = 2


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

        self.queue: list[tuple[DispatchID, function_pb.RunRequest, CallType]] = []

        self.pollers: dict[DispatchID, Poller] = {}
        self.parents: dict[DispatchID, Poller] = {}

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
                logger.debug("enqueueing call to function: %s", call.function)
                resp.dispatch_ids.append(dispatch_id)
                run_request = function_pb.RunRequest(
                    function=call.function,
                    input=call.input,
                )
                self.queue.append((dispatch_id, run_request, CallType.CALL))

            self._work_signal.notify()

        return resp

    def _validate_authentication(self, context: grpc.ServicerContext):
        expected = f"Bearer {self.api_key}"
        for key, value in context.invocation_metadata():
            if key == "authorization":
                if value == expected:
                    return
                logger.warning(
                    "a client attempted to dispatch a function call with an incorrect API key. Is the client's DISPATCH_API_KEY correct?"
                )
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
            dispatch_id, request, call_type = self.queue.pop(0)

            match call_type:
                case CallType.CALL:
                    logger.info("calling function %s", request.function)
                case CallType.RESUME:
                    logger.info("resuming function %s", request.function)
                case CallType.RETRY:
                    logger.info("retrying function %s", request.function)

            try:
                response = self.endpoint_client.run(request)
            except:
                logger.warning("call to function %s failed", request.function)
                self.queue.extend(_next_queue)
                self.queue.append((dispatch_id, request, CallType.RETRY))
                raise

            if self.roundtrips is not None:
                try:
                    roundtrips = self.roundtrips[dispatch_id]
                except KeyError:
                    roundtrips = []

                roundtrips.append((request, response))
                self.roundtrips[dispatch_id] = roundtrips

            status = Status(response.status)
            if status == Status.OK:
                logger.info("call to function %s succeeded", request.function)
            else:
                logger.warning(
                    "call to function %s failed (%s)",
                    request.function,
                    status,
                )

            if status in self.retry_on_status:
                _next_queue.append((dispatch_id, request, CallType.RETRY))

            elif response.HasField("poll"):
                assert not response.HasField("exit")

                logger.info("suspending function %s", request.function)

                logger.debug("registering poller %s", dispatch_id)

                assert dispatch_id not in self.pollers
                poller = Poller(
                    id=dispatch_id,
                    function=request.function,
                    coroutine_state=response.poll.coroutine_state,
                    waiting={},
                    results={},
                )
                self.pollers[dispatch_id] = poller

                for call in response.poll.calls:
                    child_dispatch_id = self._make_dispatch_id()
                    child_request = function_pb.RunRequest(
                        function=call.function,
                        input=call.input,
                    )

                    _next_queue.append(
                        (child_dispatch_id, child_request, CallType.CALL)
                    )
                    self.parents[child_dispatch_id] = poller
                    poller.waiting[child_dispatch_id] = call

            else:
                assert response.HasField("exit")

                if response.exit.HasField("tail_call"):
                    tail_call = response.exit.tail_call
                    logger.debug(
                        "enqueueing tail call for %s",
                        tail_call.function,
                    )
                    tail_call_request = function_pb.RunRequest(
                        function=tail_call.function,
                        input=tail_call.input,
                    )
                    _next_queue.append((dispatch_id, tail_call_request, CallType.CALL))

                elif dispatch_id in self.parents:
                    result = response.exit.result
                    poller = self.parents[dispatch_id]
                    logger.debug(
                        "notifying poller %s of call result %s", poller.id, dispatch_id
                    )

                    call = poller.waiting[dispatch_id]
                    result.correlation_id = call.correlation_id
                    poller.results[dispatch_id] = result
                    del self.parents[dispatch_id]
                    del poller.waiting[dispatch_id]

                    logger.debug(
                        "poller %s has %d waiting and %d ready results",
                        poller.id,
                        len(poller.waiting),
                        len(poller.results),
                    )

                    if not poller.waiting:
                        logger.debug(
                            "poller %s is now ready; enqueueing delivery of %d call result(s)",
                            poller.id,
                            len(poller.results),
                        )
                        poll_results_request = function_pb.RunRequest(
                            function=poller.function,
                            poll_result=poll_pb.PollResult(
                                coroutine_state=poller.coroutine_state,
                                results=poller.results.values(),
                            ),
                        )
                        del self.pollers[poller.id]
                        _next_queue.append(
                            (poller.id, poll_results_request, CallType.RESUME)
                        )

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

            try:
                self.dispatch_calls()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error(
                        "error dispatching function call to endpoint (403). Is the endpoint's DISPATCH_VERIFICATION_KEY correct?"
                    )
                else:
                    logger.exception(e)
            except httpx.ConnectError as e:
                logger.error(
                    "error connecting to the endpoint. Is it running and accessible from DISPATCH_ENDPOINT_URL?"
                )
            except Exception as e:
                logger.exception(e)

            # Introduce an artificial delay before continuing with
            # follow-up work (retries, dispatching nested calls).
            # This serves two purposes. Firstly, this is just a mock
            # Dispatch server providing the bare minimum of functionality.
            # Since there's no adaptive concurrency control, and no backoff
            # between call attempts, the mock server may busy-loop without
            # some sort of delay. Secondly, a bit of latency mimics the
            # latency you would see in a production system and makes the
            # log output easier to parse.
            time.sleep(0.15)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


@dataclass
class Poller:
    id: DispatchID
    function: str

    coroutine_state: bytes
    # TODO: support max_wait/min_results/max_results

    waiting: dict[DispatchID, call_pb.Call]
    results: dict[DispatchID, call_pb.CallResult]
