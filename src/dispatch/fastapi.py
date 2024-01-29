"""Integration of Dispatch programmable endpoints for FastAPI.

"""

import os
import fastapi
from fastapi.responses import PlainTextResponse


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
    api_url = api_url or "https://api.stealthrocket.cloud"

    if not app:
        raise ValueError("app is required")
    if not api_key:
        raise ValueError("api_key is required")
    if not api_url:
        raise ValueError("api_url is required")
    if not mount_path:
        raise ValueError("mount_path is required")

    dispatch_app = fastapi.FastAPI()

    @dispatch_app.get("/", response_class=PlainTextResponse)
    def read_root():
        return "ok"

    app.mount(mount_path, dispatch_app)
