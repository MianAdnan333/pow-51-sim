from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class OutPoint:
    tx_id: str
    index: int


@dataclass(frozen=True)
class TxOutput:
    recipient: str
    amount: int


@dataclass(frozen=True)
class Transaction:
    inputs: tuple[OutPoint, ...]
    outputs: tuple[TxOutput, ...]
    nonce: int = 0

    def __post_init__(self) -> None:
        if not self.outputs:
            raise ValueError("transaction needs at least one output")
        if any(output.amount <= 0 for output in self.outputs):
            raise ValueError("output amounts must be positive")

    @property
    def is_coinbase(self) -> bool:
        return not self.inputs

    @property
    def total_out(self) -> int:
        return sum(output.amount for output in self.outputs)

    @property
    def tx_id(self) -> str:
        spent = ",".join(f"{i.tx_id}:{i.index}" for i in self.inputs)
        paid = ",".join(f"{o.recipient}:{o.amount}" for o in self.outputs)
        return sha256(f"{spent}|{paid}|{self.nonce}".encode()).hexdigest()
