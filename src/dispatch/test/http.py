from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass
class HttpResponse(Protocol):
    status_code: int
    body: bytes

    def raise_for_status(self):
        """Raise an exception on non-2xx responses."""
        ...


class HttpClient(Protocol):
    """Protocol for HTTP clients."""

    def get(self, url: str, headers: Mapping[str, str] = {}) -> HttpResponse:
        """Make a GET request."""
        ...

    def post(
        self, url: str, body: bytes, headers: Mapping[str, str] = {}
    ) -> HttpResponse:
        """Make a POST request."""
        ...

    def url_for(self, path: str) -> str:
        """Get the fully-qualified URL for a path."""
        ...
