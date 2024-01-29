"""Integration of Dispatch programmable endpoints for FastAPI.

"""

import ring.coroutine.v1.coroutine_pb2

import os
import fastapi
import fastapi.responses
import google.protobuf.wrappers_pb2


def configure(
    app: fastapi.FastAPI,
    api_key: None | str = None,
    api_url: str = "https://api.stealthrocket.cloud",
    mount_path: str = "/dispatch",
):
    """Configure the FastAPI app to use Dispatch programmable endpoints.

    Args:
        app: The FastAPI app to configure.
        api_key: Dispatch API key to use for authentication. Uses the value of
          the DISPATCH_API_KEY environment variable by default.
        api_url: URL of the Dispatch service.
        mount_path: The path to mount Dispatch programmable endpoints at.
    """
    api_key = api_key or os.environ.get("DISPATCH_API_KEY")

    if not app:
        raise ValueError("app is required")
    if not api_key:
        raise ValueError("api_key is required")
    if not api_url:
        raise ValueError("api_url is required")
    if not mount_path:
        raise ValueError("mount_path is required")

    dispatch_app = _new_app()

    app.mount(mount_path, dispatch_app)


class GRPCResponse(fastapi.Response):
    media_type = "application/grpc+proto"


def _new_app():
    app = fastapi.FastAPI()

    @app.get("/", response_class=fastapi.responses.PlainTextResponse)
    def read_root():
        return "ok"

    @app.post("/ring.coroutine.v1.ExecutorService/Execute", response_class=GRPCResponse)
    async def execute(request: fastapi.Request):
        data: bytes = await request.body()

        req = ring.coroutine.v1.coroutine_pb2.ExecuteRequest.FromString(data)

        # TODO: unpack any
        input = google.protobuf.wrappers_pb2.StringValue
        req.input.Unpack(input)

        resp = ring.coroutine.v1.coroutine_pb2.ExecuteResponse(
            coroutine_uri=req.coroutine_uri,
            coroutine_version=req.coroutine_version,
        )

        return resp.SerializeToString()

    return app
