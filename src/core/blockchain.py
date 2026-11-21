from collections.abc import Callable, Sequence
from enum import Enum

from core.block import Block
from core.consensus import BasicRule, ConsensusRule


class AddResult(Enum):
    ACCEPTED = "accepted"
    ORPHAN = "orphan"
    REJECTED = "rejected"


ReorgListener = Callable[[list[Block], list[Block]], None]
ExtendListener = Callable[[Block], None]


class Blockchain:
    """Block tree with longest-chain fork choice; the first block seen wins ties.

    `rules` is the full rule list (default: BasicRule). `on_reorg(old_chain,
    new_chain)` fires when the tip moves to a different branch, and
    `on_extend(block)` when the tip advances by one block on the same branch.
    """

    def __init__(
        self,
        rules: Sequence[ConsensusRule] | None = None,
        on_reorg: ReorgListener | None = None,
        genesis: Block | None = None,
        on_extend: ExtendListener | None = None,
    ) -> None:
        root = Block.genesis() if genesis is None else genesis
        self._rules: list[ConsensusRule] = (
            [BasicRule()] if rules is None else list(rules)
        )
        self._on_reorg = on_reorg
        self._on_extend = on_extend
        self._blocks: dict[str, Block] = {root.hash: root}
        self._heights: dict[str, int] = {root.hash: 0}
        self._main: list[Block] = [root]
        self._tip = root

    def __contains__(self, block_hash: str) -> bool:
        return block_hash in self._blocks

    @property
    def tip(self) -> Block:
        return self._tip

    def get(self, block_hash: str) -> Block | None:
        return self._blocks.get(block_hash)

    def add_block(self, block: Block) -> AddResult:
        if block.hash in self._blocks:
            return AddResult.ACCEPTED
        if block.prev_hash not in self._blocks:
            return AddResult.ORPHAN
        parent_chain = self._path_to_parent(block)
        if not all(rule.validate(block, parent_chain) for rule in self._rules):
            return AddResult.REJECTED
        height = self._heights[block.prev_hash] + 1
        self._blocks[block.hash] = block
        self._heights[block.hash] = height
        if height > self._heights[self._tip.hash]:
            self._advance_tip(block)
        return AddResult.ACCEPTED

    def main_chain(self) -> list[Block]:
        return list(self._main)

    def chain_to(self, block_hash: str) -> list[Block]:
        path: list[Block] = []
        current = self._blocks[block_hash]
        while True:
            path.append(current)
            parent = self._blocks.get(current.prev_hash)
            if parent is None:
                break
            current = parent
        path.reverse()
        return path

    def forks(self) -> list[Block]:
        """Tips of every branch, the main one included, in the order first seen."""
        parents = {block.prev_hash for block in self._blocks.values()}
        return [block for block in self._blocks.values() if block.hash not in parents]

    def orphaned_blocks(self) -> list[Block]:
        on_main = {block.hash for block in self._main}
        return [block for block in self._blocks.values() if block.hash not in on_main]

    def _path_to_parent(self, block: Block) -> list[Block]:
        if block.prev_hash == self._tip.hash:
            return list(self._main)
        return self.chain_to(block.prev_hash)

    def _advance_tip(self, block: Block) -> None:
        if block.prev_hash == self._tip.hash:
            self._main.append(block)
            self._tip = block
            if self._on_extend is not None:
                self._on_extend(block)
            return
        old_chain = list(self._main)
        self._main = self.chain_to(block.hash)
        self._tip = block
        if self._on_reorg is not None:
            self._on_reorg(old_chain, list(self._main))
