"""Simplified proof of work: a hash is valid if it starts with `bits` hex zeros.

The simulator itself uses probabilistic mining (a miner wins a round with probability
equal to its hash share). `mine` runs a real hash loop and exists only for tests.
"""

from dataclasses import replace

from core.block import Block


class Difficulty:
    DEFAULT_BITS = 2

    @staticmethod
    def meets_target(block_hash: str, bits: int = DEFAULT_BITS) -> bool:
        return block_hash.startswith("0" * bits)


def mine(
    block_template: Block,
    bits: int = Difficulty.DEFAULT_BITS,
    max_attempts: int = 10_000_000,
) -> Block:
    for offset in range(max_attempts):
        candidate = replace(block_template, nonce=block_template.nonce + offset)
        if Difficulty.meets_target(candidate.hash, bits):
            return candidate
    raise RuntimeError(f"no valid nonce found in {max_attempts} attempts")
