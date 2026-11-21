from typing import Protocol

from core.block import GENESIS_PREV_HASH, Block


class ConsensusRule(Protocol):
    def validate(self, block: Block, chain: list[Block]) -> bool:
        """`chain` is the genesis-to-parent path the block would extend."""
        ...


class BasicRule:
    def validate(self, block: Block, chain: list[Block]) -> bool:
        if not block.has_valid_hash():
            return False
        if not chain:
            return block.index == 0 and block.prev_hash == GENESIS_PREV_HASH
        parent = chain[-1]
        return (
            block.prev_hash == parent.hash
            and block.index == parent.index + 1
            and bool(block.txs)
            and block.txs[0].is_coinbase
        )
