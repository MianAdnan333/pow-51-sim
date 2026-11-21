from pow51sim.core.block import Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError


class BlockReceiver:
    """Feeds a chain with incoming blocks, buffering those that precede their parent."""

    def __init__(self, chain: Blockchain) -> None:
        self.chain = chain
        self._orphans: dict[str, list[Block]] = {}

    def submit(self, block: Block) -> None:
        if block.prev_hash not in self.chain:
            self._orphans.setdefault(block.prev_hash, []).append(block)
            return
        pending = [block]
        while pending:
            current = pending.pop()
            try:
                self.chain.add_block(current)
            except InvalidBlockError:
                continue
            pending.extend(self._orphans.pop(current.hash, []))
