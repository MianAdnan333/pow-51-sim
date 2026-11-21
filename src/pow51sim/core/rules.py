from typing import TYPE_CHECKING

from pow51sim.core.block import Block
from pow51sim.core.consensus import ConsensusRule, InvalidBlockError
from pow51sim.core.pow import ProofOfWork
from pow51sim.core.transaction import OutPoint, Transaction

if TYPE_CHECKING:
    from pow51sim.core.blockchain import Blockchain

Utxos = dict[OutPoint, int]


class IntegrityRule(ConsensusRule):
    def validate(self, block: Block, chain: "Blockchain") -> None:
        if not block.has_valid_hash():
            raise InvalidBlockError("hash does not match block contents")


class LinkageRule(ConsensusRule):
    def validate(self, block: Block, chain: "Blockchain") -> None:
        parent = chain.get(block.prev_hash)
        if parent is None or block.index != parent.index + 1:
            raise InvalidBlockError("block does not follow its parent")


class TimestampRule(ConsensusRule):
    def validate(self, block: Block, chain: "Blockchain") -> None:
        parent = chain.get(block.prev_hash)
        if parent is not None and block.timestamp < parent.timestamp:
            raise InvalidBlockError("timestamp precedes parent")


class ProofOfWorkRule(ConsensusRule):
    def __init__(self, pow_: ProofOfWork) -> None:
        self.pow = pow_

    def validate(self, block: Block, chain: "Blockchain") -> None:
        if not self.pow.meets_target(block.hash):
            raise InvalidBlockError("insufficient proof of work")


class UtxoRule(ConsensusRule):
    """Rejects spends of missing or already-spent outputs on the block's branch."""

    def validate(self, block: Block, chain: "Blockchain") -> None:
        if not block.txs:
            return
        parent = chain.get(block.prev_hash)
        if parent is None:
            raise InvalidBlockError("unknown parent")
        unspent = self._unspent_after(chain, parent)
        coinbases = 0
        for tx in block.txs:
            if tx.is_coinbase:
                coinbases += 1
                if coinbases > 1:
                    raise InvalidBlockError("more than one coinbase")
            else:
                self._check_spend(tx, unspent)
            self._apply(tx, unspent)

    @staticmethod
    def _check_spend(tx: Transaction, unspent: Utxos) -> None:
        available = 0
        for outpoint in dict.fromkeys(tx.inputs):
            if outpoint not in unspent:
                raise InvalidBlockError("input missing or already spent")
            available += unspent[outpoint]
        if len(set(tx.inputs)) != len(tx.inputs):
            raise InvalidBlockError("duplicate input in transaction")
        if tx.total_out > available:
            raise InvalidBlockError("outputs exceed inputs")

    @staticmethod
    def _apply(tx: Transaction, unspent: Utxos) -> None:
        for outpoint in tx.inputs:
            unspent.pop(outpoint, None)
        for position, output in enumerate(tx.outputs):
            unspent[OutPoint(tx.tx_id, position)] = output.amount

    def _unspent_after(self, chain: "Blockchain", tip: Block) -> Utxos:
        unspent: Utxos = {}
        for ancestor in reversed(list(chain.ancestry(tip))):
            for tx in ancestor.txs:
                self._apply(tx, unspent)
        return unspent


def default_rules() -> list[ConsensusRule]:
    return [IntegrityRule(), LinkageRule(), TimestampRule()]
