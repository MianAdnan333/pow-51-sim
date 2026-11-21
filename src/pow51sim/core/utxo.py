from pow51sim.core.block import Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.core.transaction import OutPoint, TxOutput

SpentLog = list[tuple[OutPoint, TxOutput]]


class UTXOSet:
    """Unspent outputs of the main chain, updated incrementally on tip changes."""

    def __init__(self) -> None:
        self._unspent: dict[OutPoint, TxOutput] = {}
        self._undo: dict[str, tuple[SpentLog, list[OutPoint]]] = {}

    @classmethod
    def for_chain(cls, chain: Blockchain) -> "UTXOSet":
        utxos = cls()
        for block in chain.main_chain():
            utxos.apply_block(block)
        chain.subscribe(utxos)
        return utxos

    def __len__(self) -> int:
        return len(self._unspent)

    def __contains__(self, outpoint: OutPoint) -> bool:
        return outpoint in self._unspent

    def get(self, outpoint: OutPoint) -> TxOutput | None:
        return self._unspent.get(outpoint)

    def balance(self, owner: str) -> int:
        return sum(o.amount for o in self._unspent.values() if o.recipient == owner)

    def apply_block(self, block: Block) -> None:
        """Atomic: a block spending a missing output changes nothing."""
        spent: SpentLog = []
        added: list[OutPoint] = []
        try:
            for tx in block.txs:
                for outpoint in tx.inputs:
                    spent.append((outpoint, self._take(outpoint)))
                for position, output in enumerate(tx.outputs):
                    created = OutPoint(tx.tx_id, position)
                    self._unspent[created] = output
                    added.append(created)
        except InvalidBlockError:
            self._restore(spent, added)
            raise
        self._undo[block.hash] = (spent, added)

    def rollback_block(self, block: Block) -> None:
        if block.hash not in self._undo:
            raise ValueError("block was not applied")
        spent, added = self._undo.pop(block.hash)
        self._restore(spent, added)

    def on_reorg(self, disconnected: list[Block], connected: list[Block]) -> None:
        rolled_back: list[Block] = []
        applied: list[Block] = []
        try:
            for block in disconnected:
                self.rollback_block(block)
                rolled_back.append(block)
            for block in connected:
                self.apply_block(block)
                applied.append(block)
        except InvalidBlockError:
            for block in reversed(applied):
                self.rollback_block(block)
            for block in reversed(rolled_back):
                self.apply_block(block)
            raise

    def _take(self, outpoint: OutPoint) -> TxOutput:
        output = self._unspent.pop(outpoint, None)
        if output is None:
            raise InvalidBlockError("input missing or already spent")
        return output

    def _restore(self, spent: SpentLog, added: list[OutPoint]) -> None:
        for outpoint, output in spent:
            self._unspent[outpoint] = output
        for outpoint in added:
            self._unspent.pop(outpoint, None)
