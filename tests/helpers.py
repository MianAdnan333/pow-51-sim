from pow51sim.core.block import GENESIS, Block
from pow51sim.core.transaction import OutPoint, Transaction, TxOutput


def funding_block(*amounts: int, owner: str = "alice") -> tuple[Block, list[OutPoint]]:
    tx = Transaction((), tuple(TxOutput(owner, a) for a in amounts))
    block = GENESIS.child("honest", 1, txs=(tx,))
    return block, [OutPoint(tx.tx_id, i) for i in range(len(amounts))]


def spend(outpoint: OutPoint, to: str, amount: int = 50, nonce: int = 0) -> Transaction:
    return Transaction((outpoint,), (TxOutput(to, amount),), nonce)


def extend(
    parent: Block, miner: str, *tx_groups: tuple[Transaction, ...]
) -> list[Block]:
    blocks = []
    for txs in tx_groups or ((),):
        parent = parent.child(miner, parent.timestamp + 1, txs=txs)
        blocks.append(parent)
    return blocks
