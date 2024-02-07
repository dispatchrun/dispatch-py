import unittest

from dispatch.signature import (
    Ed25519PrivateKey,
    private_key_from_bytes,
    public_key_from_bytes,
)


class TestKey(unittest.TestCase):
    def test_bytes(self):
        private = Ed25519PrivateKey.generate()
        private2 = private_key_from_bytes(private.private_bytes_raw())
        self.assertEqual(private.private_bytes_raw(), private2.private_bytes_raw())

        public = private.public_key()
        public2 = public_key_from_bytes(public.public_bytes_raw())
        self.assertEqual(public.public_bytes_raw(), public2.public_bytes_raw())
