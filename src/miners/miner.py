from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from core.block import Block
from core.blockchain import AddResult, Blockchain
from core.transaction import Transaction, coinbase

BLOCK_REWARD = 50


@dataclass(frozen=True)
class Broadcast:
    """A block to deliver to every other node; `delay` overrides the network delay."""

    block: Block
    delay: float | None = None


def to_broadcasts(blocks: Iterable[Block]) -> list[Broadcast]:
    return [Broadcast(block) for block in blocks]


class Miner(ABC):
    """A node with its own chain view. Blocks that arrive before their parent wait
    in an orphan buffer and are adopted once the parent shows up."""

    def __init__(
        self, miner_id: str, hash_share: float, chain: Blockchain | None = None
    ) -> None:
        if not 0.0 <= hash_share <= 1.0:
            raise ValueError("hash_share must be within [0, 1]")
        self.miner_id = miner_id
        self.hash_share = hash_share
        self.chain = Blockchain() if chain is None else chain
        self.mempool: list[Transaction] = []
        self._waiting: dict[str, list[Block]] = {}

    def build_block(self, timestamp: int) -> Block:
        return self._build_on(self.chain, timestamp)

    def receive_block(self, block: Block) -> AddResult:
        result = self.chain.add_block(block)
        if result is AddResult.ORPHAN:
            self._waiting.setdefault(block.prev_hash, []).append(block)
        elif result is AddResult.ACCEPTED:
            self._confirm(block)
            self._adopt_waiting(block)
        return result

    @abstractmethod
    def on_block_found(self, block: Block) -> list[Broadcast]:
        """Take in a block this miner just found; returns what to broadcast now."""

    def _build_on(self, chain: Blockchain, timestamp: int) -> Block:
        tip = chain.tip
        height = tip.index + 1
        txs = (coinbase(self.miner_id, BLOCK_REWARD, height), *self.mempool)
        return Block(height, tip.hash, self.miner_id, txs, 0, timestamp)

    def _confirm(self, block: Block) -> None:
        self.mempool = [tx for tx in self.mempool if tx not in block.txs]

    def _adopt_waiting(self, block: Block) -> None:
        ready = [block]
        while ready:
            parent = ready.pop()
            for child in self._waiting.pop(parent.hash, []):
                if self.chain.add_block(child) is AddResult.ACCEPTED:
                    self._confirm(child)
                    ready.append(child)
