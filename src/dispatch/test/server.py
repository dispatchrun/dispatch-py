import concurrent.futures

import grpc

from dispatch.sdk.v1 import dispatch_pb2_grpc as dispatch_grpc


class DispatchServer:
    """Test server for a Dispatch service. This is useful for testing
    a mock version of Dispatch locally (e.g. see
    dispatch.test.DispatchService).

    Args:
        service: Dispatch service to serve.
        hostname: Hostname to bind to.
        port: Port to bind to, or 0 to bind to any available port.
    """

    def __init__(
        self,
        service: dispatch_grpc.DispatchServiceServicer,
        hostname: str = "127.0.0.1",
        port: int = 0,
    ):
        self._thread_pool = concurrent.futures.thread.ThreadPoolExecutor()
        self._server = grpc.server(self._thread_pool)

        self._hostname = hostname
        self._port = self._server.add_insecure_port(f"{hostname}:{port}")

        dispatch_grpc.add_DispatchServiceServicer_to_server(service, self._server)

    @property
    def url(self):
        """Returns the URL of the server."""
        return f"http://{self._hostname}:{self._port}"

    def start(self):
        """Start the server."""
        self._server.start()

    def wait(self):
        """Block until the server terminates."""
        self._server.wait_for_termination()

    def stop(self):
        """Stop the server."""
        self._server.stop(0)
        self._server.wait_for_termination()
        self._thread_pool.shutdown(wait=True, cancel_futures=True)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
