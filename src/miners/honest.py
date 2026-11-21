from core.block import Block
from miners.miner import Broadcast, Miner, to_broadcasts


class HonestMiner(Miner):
    """Mines on the longest chain it knows and broadcasts every block at once."""

    def on_block_found(self, block: Block) -> list[Broadcast]:
        self.receive_block(block)
        return to_broadcasts([block])
