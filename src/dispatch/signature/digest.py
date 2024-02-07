import hashlib
import hmac

import http_sfv


def generate_content_digest(body: str | bytes) -> str:
    """Returns a SHA-512 Content-Digest header, according to
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-digest-headers-13
    """
    if isinstance(body, str):
        body = body.encode()

    digest = hashlib.sha512(body).digest()
    return str(http_sfv.Dictionary({"sha-512": digest}))


def verify_content_digest(digest_header: str | bytes, body: str | bytes):
    """Verify a SHA-512 Content-Digest header matches a request body."""
    if isinstance(body, str):
        body = body.encode()
    if isinstance(digest_header, str):
        digest_header = digest_header.encode()

    parsed_header = http_sfv.Dictionary()
    parsed_header.parse(digest_header)

    # Note: according to https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-digest-headers-13#establish-hash-algorithm-registry,
    #  sha-256 is also a valid algorithm here. Should we generalize to handle many algorithms?
    try:
        digest = parsed_header["sha-512"].value
    except KeyError:
        raise ValueError("missing content digest")

    expect_digest = hashlib.sha512(body).digest()

    if not hmac.compare_digest(digest, expect_digest):
        raise ValueError("unexpected content digest")
