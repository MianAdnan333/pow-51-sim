from dataclasses import replace

from pow51sim.core.block import GENESIS, Block
from pow51sim.core.transaction import Transaction, TxOutput


def test_genesis_is_self_consistent():
    assert GENESIS.index == 0
    assert GENESIS.has_valid_hash()


def test_hash_is_deterministic():
    assert Block.create(1, "p", "m", 5) == Block.create(1, "p", "m", 5)


def test_hash_depends_on_every_field():
    base = Block.create(1, "p", "m", 5)
    tx = Transaction((), (TxOutput("a", 1),))
    variants = [
        Block.create(2, "p", "m", 5),
        Block.create(1, "q", "m", 5),
        Block.create(1, "p", "n", 5),
        Block.create(1, "p", "m", 6),
        Block.create(1, "p", "m", 5, nonce=1),
        Block.create(1, "p", "m", 5, txs=(tx,)),
    ]
    assert all(v.hash != base.hash for v in variants)


def test_child_links_to_parent():
    child = GENESIS.child("m", 1)
    assert child.index == 1
    assert child.prev_hash == GENESIS.hash


def test_tampering_breaks_hash():
    block = Block.create(1, "p", "m", 5)
    assert not replace(block, miner_id="thief").has_valid_hash()
