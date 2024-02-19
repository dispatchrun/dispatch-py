from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
from http_message_signatures import HTTPSignatureKeyResolver


def public_key_from_pem(pem: str | bytes) -> Ed25519PublicKey:
    """Returns an Ed25519 public key given a PEM representation."""
    if isinstance(pem, str):
        pem = pem.encode()

    key = load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"unexpected public key type: {type(key)}")
    return key


def public_key_from_bytes(key: bytes) -> Ed25519PublicKey:
    """Returns an Ed25519 public key from 32 raw bytes."""
    return Ed25519PublicKey.from_public_bytes(key)


def private_key_from_pem(
    pem: str | bytes, password: bytes | None = None
) -> Ed25519PrivateKey:
    """Returns an Ed25519 private key given a PEM representation
    and optional password."""
    if isinstance(pem, str):
        pem = pem.encode()
    if isinstance(password, str):
        password = password.encode()

    key = load_pem_private_key(pem, password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"unexpected private key type: {type(key)}")
    return key


def private_key_from_bytes(key: bytes) -> Ed25519PrivateKey:
    """Returns an Ed25519 private key from 32 raw bytes."""
    return Ed25519PrivateKey.from_private_bytes(key)


@dataclass(slots=True)
class KeyResolver(HTTPSignatureKeyResolver):
    """KeyResolver provides public and private keys.

    At this time, multiple keys and/or key types are not supported.
    Keys must be Ed25519 keys and have an ID of DEFAULT_KEY_ID.
    """

    key_id: str
    public_key: Ed25519PublicKey | None = None
    private_key: Ed25519PrivateKey | None = None

    def resolve_public_key(self, key_id: str):
        if key_id != self.key_id or self.public_key is None:
            raise ValueError(f"public key '{key_id}' not available")

        return self.public_key

    def resolve_private_key(self, key_id: str):
        if key_id != self.key_id or self.private_key is None:
            raise ValueError(f"private key '{key_id}' not available")

        return self.private_key
