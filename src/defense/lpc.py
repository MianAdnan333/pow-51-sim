from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import takewhile

from core.block import Block
from core.blockchain import Blockchain, ExtendListener, ReorgListener
from core.consensus import BasicRule, ConsensusRule
from defense.comparator import ChainComparator


@dataclass(frozen=True)
class FalsePositiveEvent:
    miner_id: str
    height: int
    run_length: int


@dataclass
class SafeModeStats:
    triggers: int = 0
    rejections: int = 0
    false_positives: int = 0
    events: list[FalsePositiveEvent] = field(default_factory=list)


class LongPrivateChainRule(ConsensusRule):
    """Flags a block that makes `max_consecutive` blocks in a row from one miner.

    Safe Mode: a flagged block is checked with the ChainComparator against the current
    main chain. It is rejected only if its chain re-spends outputs differently
    (fraud); otherwise it is accepted and recorded as a false positive, so honest
    large miners are not blocked blindly. Call `attach` once the chain exists.
    """

    def __init__(
        self,
        max_consecutive: int = 6,
        comparator: ChainComparator | None = None,
        stats: SafeModeStats | None = None,
    ) -> None:
        if max_consecutive < 2:
            raise ValueError("max_consecutive must be at least 2")
        self.max_consecutive = max_consecutive
        self.stats = SafeModeStats() if stats is None else stats
        self._comparator = comparator or ChainComparator()
        self._main_chain: Callable[[], list[Block]] | None = None

    def attach(self, chain: Blockchain) -> None:
        self._main_chain = chain.main_chain

    def validate(self, block: Block, chain: list[Block]) -> bool:
        run = self._run_length(block, chain)
        if run < self.max_consecutive:
            return True
        self.stats.triggers += 1
        if self._is_fraudulent(block, chain):
            self.stats.rejections += 1
            return False
        self.stats.false_positives += 1
        self.stats.events.append(FalsePositiveEvent(block.miner_id, block.index, run))
        return True

    def _run_length(self, block: Block, chain: list[Block]) -> int:
        same_miner = takewhile(lambda b: b.miner_id == block.miner_id, reversed(chain))
        return 1 + sum(1 for _ in same_miner)

    def _is_fraudulent(self, block: Block, chain: list[Block]) -> bool:
        if self._main_chain is None:
            raise RuntimeError("attach the rule to a Blockchain first")
        result = self._comparator.compare(self._main_chain(), [*chain, block])
        return result.is_fraudulent


def build_chain(
    defense: bool,
    max_consecutive: int = 6,
    on_reorg: ReorgListener | None = None,
    on_extend: ExtendListener | None = None,
) -> tuple[Blockchain, SafeModeStats]:
    """A Blockchain with BasicRule, plus the LPC rule when `defense` is True."""
    stats = SafeModeStats()
    rules: list[ConsensusRule] = [BasicRule()]
    lpc: LongPrivateChainRule | None = None
    if defense:
        lpc = LongPrivateChainRule(max_consecutive, stats=stats)
        rules.append(lpc)
    chain = Blockchain(rules, on_reorg=on_reorg, on_extend=on_extend)
    if lpc is not None:
        lpc.attach(chain)
    return chain, stats
