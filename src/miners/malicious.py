from core.block import Block
from core.blockchain import Blockchain
from miners.miner import Broadcast, Miner, to_broadcasts


class MaliciousMiner(Miner):
    """Building blocks for an attack; the strategy that uses them lives elsewhere.

    `chain` is the miner's view of the public chain. After `fork_from`, found blocks
    go to a separate private chain that is validated by structure only and is never
    broadcast until `release`. Without a private fork it mines like an honest miner.
    """

    def __init__(
        self, miner_id: str, hash_share: float, chain: Blockchain | None = None
    ) -> None:
        super().__init__(miner_id, hash_share, chain)
        self.private = Blockchain()
        self._fork_height: int | None = None

    @property
    def private_active(self) -> bool:
        return self._fork_height is not None

    def fork_from(self, block_hash: str) -> None:
        """Start a private branch at a public block (KeyError if it is unknown)."""
        public_path = self.chain.chain_to(block_hash)
        private = Blockchain()
        for block in public_path[1:]:
            private.add_block(block)
        self.private = private
        self._fork_height = public_path[-1].index

    def build_block(self, timestamp: int) -> Block:
        chain = self.private if self.private_active else self.chain
        return self._build_on(chain, timestamp)

    def mine_private(self, timestamp: int) -> Block:
        if not self.private_active:
            raise RuntimeError("call fork_from before mining privately")
        block = self._build_on(self.private, timestamp)
        self.private.add_block(block)
        self._confirm(block)
        return block

    def should_release(self, public_tip_height: int) -> bool:
        return self.private_active and self.private.tip.index > public_tip_height

    def release(self) -> list[Block]:
        """Return the private blocks for broadcasting and merge them into `chain`."""
        if self._fork_height is None:
            return []
        blocks = self.private.main_chain()[self._fork_height + 1 :]
        for block in blocks:
            self.receive_block(block)
        self._fork_height = None
        return blocks

    def on_block_found(self, block: Block) -> list[Broadcast]:
        if self.private_active:
            self.private.add_block(block)
            self._confirm(block)
            return []
        self.receive_block(block)
        return to_broadcasts([block])
