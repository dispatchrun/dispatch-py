from datetime import datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from http_message_signatures import HTTPMessageSigner, HTTPMessageVerifier

from .config import COVERED_COMPONENT_IDS, DEFAULT_KEY_ID, LABEL, SIGNATURE_ALGORITHM
from .digest import generate_content_digest, verify_content_digest
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

    signer = HTTPMessageSigner(
        signature_algorithm=SIGNATURE_ALGORITHM,
        key_resolver=KeyResolver(private_key=key),
    )
    signer.sign(
        request,
        key_id=DEFAULT_KEY_ID,
        covered_component_ids=COVERED_COMPONENT_IDS,
        created=created,
        label=LABEL,
        include_alg=True,
    )


def verify_request(request: Request, key: Ed25519PublicKey, max_age: timedelta):
    """Verify a request containing an HTTP Message Signature.

    The function checks three additional headers: Content-Digest,
    Signature-Input, and Signature. See the following spec for more details:
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-message-signatures

    The function checks signatures that cover at least the request method, the
    URL host and path, the Content-Type header, and the request body (via the
    Content-Digest header). At this time, signatures must use a hard-coded key
    ID of "default".

    Args:
        request: The request to verify.
        key: The Ed25519 public key to use to verify the signature.
        max_age: The maximum age of the signature.
    """
    key_resolver = KeyResolver(public_key=key)
    verifier = HTTPMessageVerifier(
        signature_algorithm=SIGNATURE_ALGORITHM, key_resolver=key_resolver
    )
    results = verifier.verify(request, max_age=max_age)

    if not results:
        raise ValueError("request does not contain any signatures")

    # TODO: check all required components are covered

    verify_content_digest(request.headers["Content-Digest"], request.body)
