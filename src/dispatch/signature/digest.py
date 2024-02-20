import hashlib
import hmac

import http_sfv
from http_message_signatures import InvalidSignature


def generate_content_digest(body: str | bytes) -> str:
    """Returns a SHA-512 Content-Digest header, according to
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-digest-headers-13
    """
    if isinstance(body, str):
        body = body.encode()

    digest = hashlib.sha512(body).digest()
    return str(http_sfv.Dictionary({"sha-512": digest}))


def verify_content_digest(digest_header: str | bytes, body: str | bytes):
    """Verify a SHA-256 or SHA-512 Content-Digest header matches a
    request body."""
    if isinstance(body, str):
        body = body.encode()
    if isinstance(digest_header, str):
        digest_header = digest_header.encode()

    parsed_header = http_sfv.Dictionary()
    parsed_header.parse(digest_header)

    # See https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-digest-headers-13#establish-hash-algorithm-registry
    if "sha-512" in parsed_header:
        digest = parsed_header["sha-512"].value
        expect_digest = hashlib.sha512(body).digest()
    elif "sha-256" in parsed_header:
        digest = parsed_header["sha-256"].value
        expect_digest = hashlib.sha256(body).digest()
    else:
        raise ValueError("missing content digest in http request header")

    if not hmac.compare_digest(digest, expect_digest):
        raise InvalidSignature(
            "digest of the request body does not match the Content-Digest header"
        )
