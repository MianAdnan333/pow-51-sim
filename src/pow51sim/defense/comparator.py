from collections.abc import Sequence
from dataclasses import dataclass

from pow51sim.core.block import Block
from pow51sim.core.transaction import OutPoint, Transaction


@dataclass(frozen=True)
class SpendConflict:
    outpoint: OutPoint
    honest_tx: Transaction
    competing_tx: Transaction


@dataclass(frozen=True)
class ComparisonReport:
    fork_index: int
    conflicts: tuple[SpendConflict, ...]

    @property
    def fraudulent(self) -> bool:
        return bool(self.conflicts)


class ChainComparator:
    """Flags a competing chain that re-spends outputs differently from the honest one.

    Both arguments are genesis-first block sequences, e.g. `Blockchain.main_chain()`.
    Only blocks after the fork point are compared; shared history cannot conflict.
    """

    def compare(
        self, honest: Sequence[Block], competing: Sequence[Block]
    ) -> ComparisonReport:
        shared = self._shared_prefix_length(honest, competing)
        honest_spends = self._spends(honest[shared:])
        conflicts = [
            SpendConflict(outpoint, honest_tx, tx)
            for block in competing[shared:]
            for tx in block.txs
            for outpoint in tx.inputs
            if (honest_tx := honest_spends.get(outpoint)) is not None
            and honest_tx.outputs != tx.outputs
        ]
        fork_index = honest[shared - 1].index if shared else -1
        return ComparisonReport(fork_index, tuple(conflicts))

    @staticmethod
    def _shared_prefix_length(a: Sequence[Block], b: Sequence[Block]) -> int:
        shared = 0
        for left, right in zip(a, b, strict=False):
            if left.hash != right.hash:
                break
            shared += 1
        return shared

    @staticmethod
    def _spends(blocks: Sequence[Block]) -> dict[OutPoint, Transaction]:
        spends: dict[OutPoint, Transaction] = {}
        for block in blocks:
            for tx in block.txs:
                for outpoint in tx.inputs:
                    spends.setdefault(outpoint, tx)
        return spends
