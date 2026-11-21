from pow51sim.core.block import Block
from pow51sim.miners.base import Miner


class HonestMiner(Miner):
    """Broadcasts every block immediately and follows the longest chain it has seen."""

    def receive(self, block: Block) -> list[Block]:
        self._receiver.submit(block)
        return []

    def _on_mined(self, block: Block) -> list[Block]:
        return [block]
