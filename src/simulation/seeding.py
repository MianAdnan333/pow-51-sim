from hashlib import sha256


def derive_seed(base: int, share: float, depth: int, trial: int) -> int:
    """Stable per-trial seed; independent of the defense mode so modes are paired."""
    digest = sha256(f"{base}|{share:.4f}|{depth}|{trial}".encode()).digest()
    return int.from_bytes(digest[:4], "big")
