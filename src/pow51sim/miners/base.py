from abc import ABC, abstractmethod

from pow51sim.core.block import Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.core.transaction import Transaction
from pow51sim.miners.receiver import BlockReceiver


class Miner(ABC):
    """`hash_power` is the miner's fraction (0-1) of total network hash rate."""

    def __init__(self, miner_id: str, hash_power: float, chain: Blockchain) -> None:
        if not 0.0 <= hash_power <= 1.0:
            raise ValueError("hash_power must be within [0, 1]")
        self.miner_id = miner_id
        self.hash_power = hash_power
        self.chain = chain
        self.last_mined: Block | None = None
        self._receiver = BlockReceiver(chain)

    def mine(self, timestamp: int, txs: tuple[Transaction, ...] = ()) -> list[Block]:
        """Mine on the local tip; returns the blocks to broadcast now.

        A block the miner's own chain rejects is discarded (`last_mined` is None).
        """
        block = self.chain.tip.child(self.miner_id, timestamp, txs)
        self.last_mined = None
        try:
            self.chain.add_block(block)
        except InvalidBlockError:
            return []
        self.last_mined = block
        return self._on_mined(block)

    @abstractmethod
    def receive(self, block: Block) -> list[Block]:
        """Take in a block from the network; returns the blocks to broadcast now."""

    @abstractmethod
    def _on_mined(self, block: Block) -> list[Block]: ...
