from dataclasses import dataclass

from pow51sim.core.block import Block
from pow51sim.core.transaction import Transaction


@dataclass(frozen=True)
class ProofOfWork:
    """Hash must fall below a target with `difficulty_bits` leading zero bits."""

    difficulty_bits: int = 0
    max_attempts: int = 1_000_000

    def meets_target(self, block_hash: str) -> bool:
        return int(block_hash, 16) < 1 << (256 - self.difficulty_bits)

    def mine(
        self,
        index: int,
        prev_hash: str,
        miner_id: str,
        timestamp: int,
        txs: tuple[Transaction, ...] = (),
    ) -> Block:
        for nonce in range(self.max_attempts):
            block = Block.create(index, prev_hash, miner_id, timestamp, txs, nonce)
            if self.meets_target(block.hash):
                return block
        raise RuntimeError("no valid nonce found within max_attempts")
