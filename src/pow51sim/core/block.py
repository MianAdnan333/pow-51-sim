from dataclasses import dataclass
from hashlib import sha256

from pow51sim.core.transaction import Transaction


@dataclass(frozen=True)
class Block:
    index: int
    prev_hash: str
    miner_id: str
    txs: tuple[Transaction, ...]
    nonce: int
    timestamp: int
    hash: str

    @staticmethod
    def compute_hash(
        index: int,
        prev_hash: str,
        miner_id: str,
        txs: tuple[Transaction, ...],
        nonce: int,
        timestamp: int,
    ) -> str:
        tx_ids = ",".join(tx.tx_id for tx in txs)
        payload = f"{index}|{prev_hash}|{miner_id}|{tx_ids}|{nonce}|{timestamp}"
        return sha256(payload.encode()).hexdigest()

    @classmethod
    def create(
        cls,
        index: int,
        prev_hash: str,
        miner_id: str,
        timestamp: int,
        txs: tuple[Transaction, ...] = (),
        nonce: int = 0,
    ) -> "Block":
        digest = cls.compute_hash(index, prev_hash, miner_id, txs, nonce, timestamp)
        return cls(index, prev_hash, miner_id, txs, nonce, timestamp, digest)

    def child(
        self,
        miner_id: str,
        timestamp: int,
        txs: tuple[Transaction, ...] = (),
        nonce: int = 0,
    ) -> "Block":
        return Block.create(self.index + 1, self.hash, miner_id, timestamp, txs, nonce)

    def has_valid_hash(self) -> bool:
        expected = self.compute_hash(
            self.index,
            self.prev_hash,
            self.miner_id,
            self.txs,
            self.nonce,
            self.timestamp,
        )
        return self.hash == expected


GENESIS = Block.create(index=0, prev_hash="", miner_id="genesis", timestamp=0)
