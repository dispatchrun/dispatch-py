from dataclasses import dataclass

from http_message_signatures.structures import CaseInsensitiveDict


@dataclass(slots=True)
class Request:
    """A framework-agnostic representation of an HTTP request."""

    method: str
    url: str
    headers: CaseInsensitiveDict
    body: str | bytes
