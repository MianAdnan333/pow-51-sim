from collections.abc import Sequence
from dataclasses import dataclass

from core.block import Block
from core.transaction import OutPoint


@dataclass(frozen=True)
class ComparisonResult:
    is_fraudulent: bool
    conflicting_outpoints: tuple[OutPoint, ...]
    fork_height: int


class ChainComparator:
    """Finds outputs spent by different transactions on the two sides of a fork.

    Chains are genesis-first block sequences. Only blocks after the fork point are
    compared, since shared history cannot conflict.
    """

    def compare(
        self, honest_chain: Sequence[Block], competing_chain: Sequence[Block]
    ) -> ComparisonResult:
        shared = self._shared_prefix(honest_chain, competing_chain)
        honest_spends = self._spends(honest_chain[shared:])
        conflicts: dict[OutPoint, None] = {}
        for block in competing_chain[shared:]:
            for tx in block.txs:
                for outpoint in tx.inputs:
                    other = honest_spends.get(outpoint)
                    if other is not None and other != tx.tx_id:
                        conflicts[outpoint] = None
        fork_height = honest_chain[shared - 1].index if shared else -1
        return ComparisonResult(bool(conflicts), tuple(conflicts), fork_height)

    @staticmethod
    def _shared_prefix(a: Sequence[Block], b: Sequence[Block]) -> int:
        shared = 0
        for left, right in zip(a, b, strict=False):
            if left.hash != right.hash:
                break
            shared += 1
        return shared

    @staticmethod
    def _spends(blocks: Sequence[Block]) -> dict[OutPoint, str]:
        spends: dict[OutPoint, str] = {}
        for block in blocks:
            for tx in block.txs:
                for outpoint in tx.inputs:
                    spends.setdefault(outpoint, tx.tx_id)
        return spends
