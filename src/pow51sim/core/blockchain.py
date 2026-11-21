from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import takewhile
from typing import Protocol

from pow51sim.core.block import GENESIS, Block
from pow51sim.core.consensus import ConsensusRule, InvalidBlockError
from pow51sim.core.rules import default_rules


@dataclass(frozen=True)
class AddResult:
    became_tip: bool
    reorg_depth: int = 0


class ChainListener(Protocol):
    def on_reorg(self, disconnected: list[Block], connected: list[Block]) -> None:
        """Called before the tip moves. `disconnected` is newest-first, `connected`
        oldest-first. Raising InvalidBlockError vetoes the block."""


class Blockchain:
    """Block tree with longest-chain fork choice; first seen wins ties.

    Listeners are not carried over by `copy`.
    """

    def __init__(
        self, rules: Sequence[ConsensusRule] | None = None, genesis: Block = GENESIS
    ) -> None:
        self._rules = tuple(default_rules() if rules is None else rules)
        self._genesis = genesis
        self._blocks: dict[str, Block] = {genesis.hash: genesis}
        self._children: dict[str, list[str]] = {genesis.hash: []}
        self._tip = genesis
        self._listeners: list[ChainListener] = []

    def __len__(self) -> int:
        return len(self._blocks)

    def __contains__(self, block_hash: str) -> bool:
        return block_hash in self._blocks

    @property
    def tip(self) -> Block:
        return self._tip

    @property
    def height(self) -> int:
        return self._tip.index

    def get(self, block_hash: str) -> Block | None:
        return self._blocks.get(block_hash)

    def subscribe(self, listener: ChainListener) -> None:
        self._listeners.append(listener)

    def add_block(self, block: Block) -> AddResult:
        if block.hash in self._blocks:
            return AddResult(became_tip=False)
        if block.prev_hash not in self._blocks:
            raise InvalidBlockError("unknown parent")
        for rule in self._rules:
            rule.validate(block, self)
        if block.index <= self._tip.index:
            self._store(block)
            return AddResult(became_tip=False)
        depth = self._switch_tip_to(block)
        self._store(block)
        self._tip = block
        return AddResult(became_tip=True, reorg_depth=depth)

    def ancestry(self, block: Block) -> Iterator[Block]:
        current: Block | None = block
        while current is not None:
            yield current
            current = self._blocks.get(current.prev_hash)

    def branch(self, tip: Block) -> list[Block]:
        return list(reversed(list(self.ancestry(tip))))

    def main_chain(self) -> list[Block]:
        return self.branch(self._tip)

    def tips(self) -> list[Block]:
        return [self._blocks[h] for h, kids in self._children.items() if not kids]

    def fork_tips(self) -> list[Block]:
        return [tip for tip in self.tips() if tip.hash != self._tip.hash]

    def common_ancestor(self, a: Block, b: Block) -> Block:
        while a.hash != b.hash:
            if a.index >= b.index:
                a = self._blocks[a.prev_hash]
            else:
                b = self._blocks[b.prev_hash]
        return a

    def validate(self, rules: Sequence[ConsensusRule] | None = None) -> bool:
        active = self._rules if rules is None else tuple(rules)
        try:
            for block in self.main_chain()[1:]:
                for rule in active:
                    rule.validate(block, self)
        except InvalidBlockError:
            return False
        return True

    def copy(self, rules: Sequence[ConsensusRule] | None = None) -> "Blockchain":
        clone = Blockchain(self._rules if rules is None else rules, self._genesis)
        clone._blocks = dict(self._blocks)
        clone._children = {h: list(kids) for h, kids in self._children.items()}
        clone._tip = self._tip
        return clone

    def _switch_tip_to(self, block: Block) -> int:
        parent = self._blocks[block.prev_hash]
        ancestor = self.common_ancestor(self._tip, parent)
        disconnected = self._blocks_above(self._tip, ancestor)
        connected = [*reversed(self._blocks_above(parent, ancestor)), block]
        for listener in self._listeners:
            listener.on_reorg(disconnected, connected)
        return len(disconnected)

    def _blocks_above(self, start: Block, ancestor: Block) -> list[Block]:
        return list(takewhile(lambda b: b.hash != ancestor.hash, self.ancestry(start)))

    def _store(self, block: Block) -> None:
        self._blocks[block.hash] = block
        self._children[block.hash] = []
        self._children[block.prev_hash].append(block.hash)
