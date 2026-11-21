from dataclasses import dataclass, field

from core.hash_utils import hash_fields
from core.transaction import Transaction

GENESIS_PREV_HASH = "0" * 64


@dataclass(frozen=True)
class Block:
    index: int
    prev_hash: str
    miner_id: str
    txs: tuple[Transaction, ...]
    nonce: int
    timestamp: int
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hash", self.compute_hash())

    def compute_hash(self) -> str:
        return hash_fields(
            self.index,
            self.prev_hash,
            self.miner_id,
            [tx.tx_id for tx in self.txs],
            self.nonce,
            self.timestamp,
        )

    def has_valid_hash(self) -> bool:
        return self.hash == self.compute_hash()

    @classmethod
    def genesis(cls) -> "Block":
        return cls(0, GENESIS_PREV_HASH, "genesis", (), 0, 0)
