import unittest

from dispatch.signature.digest import generate_content_digest, verify_content_digest

STRINGS = ("", "x", '{"hello": "world"}')


class TestDigest(unittest.TestCase):
    def test_sha512(self):
        for value in STRINGS:
            digest_header = generate_content_digest(value)
            verify_content_digest(digest_header, value)

    def test_known_digests(self):
        known = {
            '{"hello": "world"}': "sha-512=:WZDPaVn/7XgHaAy8pmojAkGWoRx2UFChF41A2svX+TaPm+AbwAgBWnrIiYllu7BNNyealdVLvRwEmTHWXvJwew==:",
        }
        for value, digest_header in known.items():
            verify_content_digest(digest_header, value)
