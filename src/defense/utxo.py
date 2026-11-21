from collections.abc import Sequence

from core.block import Block
from core.transaction import OutPoint, TxOutput

SpentLog = list[tuple[OutPoint, TxOutput]]


class UTXOSet:
    """Unspent outputs of the main chain.

    Wire it up with `Blockchain(on_reorg=utxo.on_reorg, on_extend=utxo.apply_block)`.
    It tracks state and does not validate: spends of unknown outputs are ignored.
    """

    def __init__(self) -> None:
        self._unspent: dict[OutPoint, TxOutput] = {}
        self._undo: dict[str, tuple[SpentLog, list[OutPoint]]] = {}

    def __len__(self) -> int:
        return len(self._unspent)

    def is_unspent(self, outpoint: OutPoint) -> bool:
        return outpoint in self._unspent

    def get(self, outpoint: OutPoint) -> TxOutput | None:
        return self._unspent.get(outpoint)

    def balance(self, owner: str) -> int:
        return sum(o.amount for o in self._unspent.values() if o.owner == owner)

    def apply_block(self, block: Block) -> None:
        spent: SpentLog = []
        created: list[OutPoint] = []
        for tx in block.txs:
            for outpoint in tx.inputs:
                output = self._unspent.pop(outpoint, None)
                if output is not None:
                    spent.append((outpoint, output))
            for position, output in enumerate(tx.outputs):
                new_point = OutPoint(tx.tx_id, position)
                self._unspent[new_point] = output
                created.append(new_point)
        self._undo[block.hash] = (spent, created)

    def rollback_block(self, block: Block) -> None:
        if block.hash not in self._undo:
            raise ValueError("block was not applied")
        spent, created = self._undo.pop(block.hash)
        for outpoint, output in spent:
            self._unspent[outpoint] = output
        for outpoint in created:
            self._unspent.pop(outpoint, None)

    def rebuild(self, chain: Sequence[Block]) -> None:
        self._unspent.clear()
        self._undo.clear()
        for block in chain:
            self.apply_block(block)

    def on_reorg(self, old_chain: list[Block], new_chain: list[Block]) -> None:
        shared = 0
        for old, new in zip(old_chain, new_chain, strict=False):
            if old.hash != new.hash:
                break
            shared += 1
        for block in reversed(old_chain[shared:]):
            self.rollback_block(block)
        for block in new_chain[shared:]:
            self.apply_block(block)
