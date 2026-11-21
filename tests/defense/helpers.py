from core.block import Block
from core.blockchain import AddResult, Blockchain
from core.transaction import OutPoint, Transaction, TxOutput, coinbase

GENESIS = Block.genesis()


def block_on(
    parent: Block,
    miner: str = "m",
    txs: tuple[Transaction, ...] = (),
    timestamp: int | None = None,
) -> Block:
    height = parent.index + 1
    stamp = height if timestamp is None else timestamp
    return Block(
        height, parent.hash, miner, (coinbase(miner, 50, height), *txs), 0, stamp
    )


def funding_block(*amounts: int, owner: str = "alice") -> tuple[Block, list[OutPoint]]:
    outputs = tuple(TxOutput(owner, amount) for amount in amounts)
    tx = Transaction((), outputs, nonce=1)
    block = Block(1, GENESIS.hash, "faucet", (tx,), 0, 0)
    return block, [OutPoint(tx.tx_id, i) for i in range(len(amounts))]


def spend(coin: OutPoint, to: str, amount: int = 50) -> Transaction:
    return Transaction((coin,), (TxOutput(to, amount),))


def add_run(chain: Blockchain, parent: Block, miners: list[str]) -> list[Block]:
    blocks: list[Block] = []
    for miner in miners:
        parent = block_on(parent, miner)
        assert chain.add_block(parent) is not AddResult.ORPHAN
        blocks.append(parent)
    return blocks
