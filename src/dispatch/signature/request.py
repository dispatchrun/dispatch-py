from dataclasses import dataclass


@dataclass
class Request:
    """A framework-agnostic representation of an HTTP request."""

    method: str
    url: str
    headers: dict[str, str]
    body: str | bytes
