import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Sequence, Set, Union, cast
from urllib.parse import urlparse

import http_sfv
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from http_message_signatures import (
    HTTPMessageSigner,
    HTTPMessageVerifier,
    InvalidSignature,
    VerifyResult,
)
from http_message_signatures.algorithms import ED25519
from http_message_signatures.structures import CaseInsensitiveDict

from .digest import generate_content_digest, verify_content_digest
from .key import (
    KeyResolver,
    private_key_from_bytes,
    private_key_from_pem,
    public_key_from_bytes,
    public_key_from_pem,
)
from .request import Request

ALGORITHM = ED25519
DEFAULT_KEY_ID = "default"

COVERED_COMPONENT_IDS = {
    "@method",
    "@path",
    "@authority",
    "content-type",
    "content-digest",
}

logger = logging.getLogger(__name__)


def sign_request(request: Request, key: Ed25519PrivateKey, created: datetime):
    """Sign a request using HTTP Message Signatures.

    The function adds three additional headers: Content-Digest,
    Signature-Input, and Signature. See the following spec for more details:
    https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-message-signatures

    The signature covers the request method, the URL host and path, the
    Content-Type header, and the request body. At this time, an ED25519
    signature is generated with a hard-coded key ID of "default".

    Args:
        request: The request to sign.
        key: The Ed25519 private key to use to generate the signature.
        created: The times at which the signature is created.
    """
    logger.debug("signing request with %d byte body", len(request.body))
    request.headers["Content-Digest"] = generate_content_digest(request.body)

    signer = HTTPMessageSigner(
        signature_algorithm=ALGORITHM,
        key_resolver=KeyResolver(key_id=DEFAULT_KEY_ID, private_key=key),
    )
    signer.sign(
        request,
        key_id=DEFAULT_KEY_ID,
        covered_component_ids=cast(Sequence[str], COVERED_COMPONENT_IDS),
        created=created,
        label="dispatch",
        include_alg=True,
    )
    logger.debug("signed request successfully")


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
    logger.debug("verifying request signature")

    # Verify embedded signatures.
    key_resolver = KeyResolver(key_id=DEFAULT_KEY_ID, public_key=key)
    verifier = HTTPMessageVerifier(
        signature_algorithm=ALGORITHM, key_resolver=key_resolver
    )
    results = verifier.verify(request, max_age=max_age)

    # Check that at least one signature covers the required components.
    for result in results:
        covered_components = extract_covered_components(result)
        if covered_components.issuperset(COVERED_COMPONENT_IDS):
            break
    else:
        raise ValueError(
            f"no signatures found that covered all required components ({COVERED_COMPONENT_IDS})"
        )

    # Check that the Content-Digest header matches the body.
    verify_content_digest(request.headers["Content-Digest"], request.body)


def extract_covered_components(result: VerifyResult) -> Set[str]:
    covered_components: Set[str] = set()
    for key in result.covered_components.keys():
        item = http_sfv.Item()
        item.parse(key.encode())
        assert isinstance(item.value, str)
        covered_components.add(item.value)

    return covered_components


def parse_verification_key(
    verification_key: Optional[Union[Ed25519PublicKey, str, bytes]],
    endpoint: Optional[str] = None,
) -> Optional[Ed25519PublicKey]:
    # This function depends a lot on global context like enviornment variables
    # and logging configuration. It's not ideal for testing, but it's useful to
    # unify the behavior of the Dispatch class everywhere the signature module
    # is used.
    if isinstance(verification_key, Ed25519PublicKey):
        return verification_key

    # Keep track of whether the key was obtained from the environment, so that
    # we can tweak the error messages accordingly.
    from_env = False
    if not verification_key:
        try:
            verification_key = os.environ["DISPATCH_VERIFICATION_KEY"]
        except KeyError:
            return None
        from_env = verification_key is not None

    if isinstance(verification_key, bytes):
        verification_key = verification_key.decode()

    # Be forgiving when accepting keys in PEM format, which may span
    # multiple lines. Users attempting to pass a PEM key via an environment
    # variable may accidentally include literal "\n" bytes rather than a
    # newline char (0xA).
    public_key: Optional[Ed25519PublicKey] = None
    try:
        public_key = public_key_from_pem(verification_key.replace("\\n", "\n"))
    except ValueError:
        pass

    # If the key is not in PEM format, try to decode it as base64 string.
    if not public_key:
        try:
            public_key = public_key_from_bytes(
                base64.b64decode(verification_key.encode())
            )
        except ValueError:
            if from_env:
                raise ValueError(
                    f"invalid DISPATCH_VERIFICATION_KEY '{verification_key}'"
                )
            raise ValueError(f"invalid verification key '{verification_key}'")

    # Print diagostic information about the key, this is useful for debugging.
    url_scheme = ""
    if endpoint:
        try:
            parsed_url = urlparse(endpoint)
            url_scheme = parsed_url.scheme
        except:
            pass

    if public_key:
        base64_key = base64.b64encode(public_key.public_bytes_raw()).decode()
        logger.info("verifying request signatures using key %s", base64_key)
    elif url_scheme != "bridge":
        logger.warning(
            "request verification is disabled because DISPATCH_VERIFICATION_KEY is not set"
        )
    return public_key
