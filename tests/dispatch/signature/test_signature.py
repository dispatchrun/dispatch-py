import base64
import os
import unittest
from datetime import datetime, timedelta
from unittest import mock

from http_message_signatures import HTTPMessageSigner
from http_message_signatures._algorithms import ED25519

from dispatch.signature import (
    CaseInsensitiveDict,
    Ed25519PublicKey,
    InvalidSignature,
    Request,
    parse_verification_key,
    sign_request,
    verify_request,
)
from dispatch.signature.key import (
    KeyResolver,
    private_key_from_pem,
    public_key_from_pem,
)

public_key = public_key_from_pem(
    """
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=
-----END PUBLIC KEY-----
"""
)

private_key = private_key_from_pem(
    """
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF
-----END PRIVATE KEY-----
"""
)

public_key2_pem = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=
-----END PUBLIC KEY-----
"""
public_key2_pem2 = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJrQLj5P/89iXES9+vFgrIy29clF9CC/oPPsw3c5D0bs=
-----END PUBLIC KEY-----
"""
public_key2 = public_key_from_pem(public_key2_pem)
public_key2_bytes = public_key2.public_bytes_raw()
public_key2_b64 = base64.b64encode(public_key2_bytes)


class TestSignature(unittest.TestCase):
    def setUp(self):
        self.request = Request(
            method="POST",
            url="https://example.com/foo?bar=1",
            body='{"hello": "world"}',
            headers=CaseInsensitiveDict(
                {
                    "host": "example.com",
                    "content-type": "application/json",
                    "content-length": "18",
                }
            ),
        )

    def test_sign_and_verify(self):
        sign_request(self.request, private_key, created=datetime.now())

        self.assertEqual(
            self.request.headers["Content-Digest"],
            "sha-512=:WZDPaVn/7XgHaAy8pmojAkGWoRx2UFChF41A2svX+TaPm+AbwAgBWnrIiYllu7BNNyealdVLvRwEmTHWXvJwew==:",
        )
        self.assertIn("Signature-Input", self.request.headers)
        self.assertIn("Signature", self.request.headers)

        verify_request(self.request, public_key, max_age=timedelta(minutes=1))

    def test_missing_signature(self):
        with self.assertRaises(InvalidSignature):
            verify_request(self.request, public_key, max_age=timedelta(minutes=1))

    def test_signature_too_old(self):
        created = datetime.now() - timedelta(minutes=2)
        sign_request(self.request, private_key, created)
        with self.assertRaises(InvalidSignature):
            verify_request(self.request, public_key, max_age=timedelta(minutes=1))

    def test_content_digest_invalid(self):
        sign_request(self.request, private_key, datetime.now())
        self.request.body = "foo"
        with self.assertRaisesRegex(
            InvalidSignature,
            "digest of the request body does not match the Content-Digest header",
        ):
            verify_request(self.request, public_key, max_age=timedelta(minutes=1))

    def test_signature_coverage(self):
        # Manually sign the request, but do so without including the
        # Content-Digest header.
        signer = HTTPMessageSigner(
            signature_algorithm=ED25519,
            key_resolver=KeyResolver(key_id="default", private_key=private_key),
        )
        signer.sign(
            self.request,
            key_id="default",
            covered_component_ids=["@method", "@path", "@authority", "content-type"],
            created=datetime.now(),
            label="dispatch",
            include_alg=True,
        )

        with self.assertRaises(ValueError):
            verify_request(self.request, public_key, max_age=timedelta(minutes=1))

    def test_known_signature(self):
        # See:
        # https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-message-signatures#appendix-B.1.4
        # https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-message-signatures#name-test-cases
        request = Request(
            method="POST",
            url="https://example.com/foo?param=Value&Pet=dog",
            headers=CaseInsensitiveDict(
                {
                    "host": "example.com",
                    "date": "Tue, 20 Apr 2021 02:07:55 GMT",
                    "content-type": "application/json",
                    "content-length": "18",
                    "content-digest": "sha-512=:WZDPaVn/7XgHaAy8pmojAkGWoRx2UFChF41A2svX+TaPm+AbwAgBWnrIiYllu7BNNyealdVLvRwEmTHWXvJwew==:",
                    "signature-input": 'sig-b26=("date" "@method" "@path" "@authority" "content-type" "content-length");created=1618884473;keyid="test-key-ed25519"',
                    "signature": "sig-b26=:wqcAqbmYJ2ji2glfAMaRy4gruYYnx2nEFN2HN6jrnDnQCK1u02Gb04v9EDgwUPiu4A0w6vuQv5lIp5WPpBKRCw==:",
                }
            ),
            body='{"hello": "world"}',
        )

        # It's not accepted because the keyid != "default"
        with self.assertRaisesRegex(
            ValueError, "public key 'test-key-ed25519' not available"
        ):
            verify_request(request, public_key, max_age=timedelta(weeks=9000))

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": public_key2_pem})
    def test_parse_verification_key_env_pem_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": public_key2_pem2})
    def test_parse_verification_key_env_pem_escaped_newline_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    @mock.patch.dict(
        os.environ, {"DISPATCH_VERIFICATION_KEY": public_key2_b64.decode()}
    )
    def test_parse_verification_key_env_b64_str(self):
        verification_key = parse_verification_key(None)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_none(self):
        # The verification key is optional. Both Dispatch(verification_key=...) and
        # DISPATCH_VERIFICATION_KEY may be omitted/None.
        verification_key = parse_verification_key(None)
        self.assertIsNone(verification_key)

    def test_parse_verification_key_ed25519publickey(self):
        verification_key = parse_verification_key(public_key2)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_pem_str(self):
        verification_key = parse_verification_key(public_key2_pem)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_pem_escaped_newline_str(self):
        verification_key = parse_verification_key(public_key2_pem2)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_pem_bytes(self):
        verification_key = parse_verification_key(public_key2_pem.encode())
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_b64_str(self):
        verification_key = parse_verification_key(public_key2_b64.decode())
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_b64_bytes(self):
        verification_key = parse_verification_key(public_key2_b64)
        self.assertIsInstance(verification_key, Ed25519PublicKey)
        self.assertEqual(verification_key.public_bytes_raw(), public_key2_bytes)

    def test_parse_verification_key_invalid(self):
        with self.assertRaisesRegex(ValueError, "invalid verification key 'foo'"):
            parse_verification_key("foo")

    @mock.patch.dict(os.environ, {"DISPATCH_VERIFICATION_KEY": "foo"})
    def test_parse_verification_key_invalid_env(self):
        with self.assertRaisesRegex(
            ValueError, "invalid DISPATCH_VERIFICATION_KEY 'foo'"
        ):
            parse_verification_key(None)
