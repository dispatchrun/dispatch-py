import hashlib

import http_sfv


def generate_content_digest(body: str | bytes) -> str:
    """Returns a SHA-512 Content-Digest header, according to
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-digest-headers-13
    """
    if isinstance(body, str):
        body = body.encode()

    digest = hashlib.sha512(body).digest()
    return str(http_sfv.Dictionary({"sha-512": digest}))
