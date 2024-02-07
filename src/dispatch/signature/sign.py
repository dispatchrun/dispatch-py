from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from http_message_signatures import HTTPMessageSigner

from .config import COVERED_COMPONENT_IDS, DEFAULT_KEY_ID, LABEL, SIGNING_ALGORITHM
from .digest import generate_content_digest
from .key import KeyResolver
from .request import Request


def sign_request(request: Request, key: Ed25519PrivateKey, created: datetime):
    """Sign a request using HTTP Message Signatures.

    The function adds three additional headers: Content-Digest,
    Signature-Input, and Signature. See the following spec for more details:
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-message-signatures

    The signature covers the request method, the URL host and path, the
    Content-Type header, and the request body. At this time, the signature uses
    a hard-coded key ID of "default".

    Args:
        request: The request to sign.
        key: The Ed25519 private key to use to generate the signature.
        created: The times at which the signature is created.
    """
    request.headers["Content-Digest"] = generate_content_digest(request.body)

    key_resolver = KeyResolver(private_key=key)

    signer = HTTPMessageSigner(
        signature_algorithm=SIGNING_ALGORITHM, key_resolver=key_resolver
    )
    signer.sign(
        request,
        key_id=DEFAULT_KEY_ID,
        covered_component_ids=COVERED_COMPONENT_IDS,
        created=created,
        label=LABEL,
        include_alg=False,
    )

    return request.headers
