import json
from hashlib import sha256


def sha256_hex(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def hash_fields(*fields: object) -> str:
    """Hash JSON-serializable fields unambiguously (no delimiter collisions)."""
    return sha256_hex(json.dumps(fields, separators=(",", ":")))
