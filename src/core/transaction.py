from dataclasses import dataclass, field

from core.hash_utils import hash_fields


@dataclass(frozen=True)
class OutPoint:
    tx_id: str
    index: int


@dataclass(frozen=True)
class TxOutput:
    owner: str
    amount: int


@dataclass(frozen=True)
class Transaction:
    """`nonce` keeps identical transactions distinct (a coinbase uses its height)."""

    inputs: tuple[OutPoint, ...]
    outputs: tuple[TxOutput, ...]
    nonce: int = 0
    tx_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.outputs or any(out.amount <= 0 for out in self.outputs):
            raise ValueError("a transaction needs outputs with positive amounts")
        object.__setattr__(self, "tx_id", self._compute_id())

    @property
    def is_coinbase(self) -> bool:
        return not self.inputs

    def _compute_id(self) -> str:
        spent = [[point.tx_id, point.index] for point in self.inputs]
        paid = [[out.owner, out.amount] for out in self.outputs]
        return hash_fields(spent, paid, self.nonce)


def coinbase(miner_id: str, reward: int, height: int) -> Transaction:
    return Transaction(inputs=(), outputs=(TxOutput(miner_id, reward),), nonce=height)
