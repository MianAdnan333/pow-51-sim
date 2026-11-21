from core.block import Block
from core.blockchain import Blockchain
from core.transaction import coinbase


def child(parent: Block, miner: str = "m", timestamp: int | None = None) -> Block:
    height = parent.index + 1
    stamp = height if timestamp is None else timestamp
    return Block(height, parent.hash, miner, (coinbase(miner, 50, height),), 0, stamp)


def extend(
    chain: Blockchain, parent: Block, count: int, miner: str = "m"
) -> list[Block]:
    blocks: list[Block] = []
    for _ in range(count):
        parent = child(parent, miner)
        chain.add_block(parent)
        blocks.append(parent)
    return blocks
