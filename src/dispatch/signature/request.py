from dataclasses import dataclass
from typing import Union

from http_message_signatures.structures import CaseInsensitiveDict


@dataclass
class Request:
    """A framework-agnostic representation of an HTTP request."""

    method: str
    url: str
    headers: CaseInsensitiveDict
    body: Union[str, bytes]
