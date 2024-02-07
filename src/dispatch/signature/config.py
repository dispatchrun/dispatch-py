from http_message_signatures.algorithms import ED25519

LABEL = "dispatch"

SIGNATURE_ALGORITHM = ED25519

DEFAULT_KEY_ID = "default"

COVERED_COMPONENT_IDS = {
    "@method",
    "@path",
    "@authority",
    "content-type",
    "content-digest",
}
