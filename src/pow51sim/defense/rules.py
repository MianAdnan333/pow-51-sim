from itertools import islice, takewhile
from weakref import WeakSet

from pow51sim.core.block import Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import ConsensusRule, InvalidBlockError
from pow51sim.core.rules import default_rules
from pow51sim.defense.comparator import ChainComparator


class MaxReorgDepthRule(ConsensusRule):
    def __init__(self, max_depth: int) -> None:
        self.max_depth = max_depth

    def validate(self, block: Block, chain: Blockchain) -> None:
        tip = chain.tip
        if block.index <= tip.index:
            return
        parent = chain.get(block.prev_hash)
        if parent is None:
            return
        depth = tip.index - chain.common_ancestor(tip, parent).index
        if depth > self.max_depth:
            raise InvalidBlockError(f"reorg depth {depth} exceeds {self.max_depth}")


class LongPrivateChainRule(ConsensusRule):
    """Rejects a block that makes `max_consecutive` blocks in a row from one miner.

    The first rejection puts that chain in Safe Mode. From then on, every reorg is
    checked with the ChainComparator and rejected if the new branch re-spends outputs
    differently from the current main chain. Safe Mode is tracked per chain and
    never switches off.
    """

    def __init__(
        self, max_consecutive: int = 6, comparator: ChainComparator | None = None
    ) -> None:
        if max_consecutive < 2:
            raise ValueError("max_consecutive must be at least 2")
        self.max_consecutive = max_consecutive
        self._comparator = comparator or ChainComparator()
        self._safe_mode: WeakSet[Blockchain] = WeakSet()

    def safe_mode_active(self, chain: Blockchain) -> bool:
        return chain in self._safe_mode

    def validate(self, block: Block, chain: Blockchain) -> None:
        if self._run_length(block, chain) >= self.max_consecutive:
            self._safe_mode.add(chain)
            raise InvalidBlockError(
                f"{self.max_consecutive} consecutive blocks from {block.miner_id}"
            )
        if self.safe_mode_active(chain):
            self._check_reorg(block, chain)

    def _run_length(self, block: Block, chain: Blockchain) -> int:
        parent = chain.get(block.prev_hash)
        if parent is None:
            return 1
        same_miner = takewhile(
            lambda b: b.miner_id == block.miner_id, chain.ancestry(parent)
        )
        return 1 + sum(1 for _ in islice(same_miner, self.max_consecutive - 1))

    def _check_reorg(self, block: Block, chain: Blockchain) -> None:
        parent = chain.get(block.prev_hash)
        is_reorg = block.index > chain.tip.index and parent != chain.tip
        if parent is None or not is_reorg:
            return
        competing = [*chain.branch(parent), block]
        report = self._comparator.compare(chain.main_chain(), competing)
        if report.fraudulent:
            raise InvalidBlockError("reorg conflicts with spends on the main chain")


def build_rules(
    max_reorg_depth: int | None, max_consecutive: int | None = None
) -> list[ConsensusRule]:
    rules = default_rules()
    if max_reorg_depth is not None:
        rules.append(MaxReorgDepthRule(max_reorg_depth))
    if max_consecutive is not None:
        rules.append(LongPrivateChainRule(max_consecutive))
    return rules
