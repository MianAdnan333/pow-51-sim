from core.block import Block
from core.blockchain import AddResult
from core.transaction import OutPoint, Transaction, TxOutput
from miners.honest import HonestMiner
from miners.miner import BLOCK_REWARD, Broadcast

from .helpers import child

GENESIS = Block.genesis()


def test_build_block_extends_the_tip_with_a_coinbase_first():
    miner = HonestMiner("h", 0.5)
    block = miner.build_block(timestamp=7)
    assert block.index == 1
    assert block.prev_hash == GENESIS.hash
    assert block.timestamp == 7
    assert block.txs[0].is_coinbase
    assert block.txs[0].outputs[0].owner == "h"
    assert block.txs[0].outputs[0].amount == BLOCK_REWARD


def test_mempool_transactions_follow_the_coinbase():
    miner = HonestMiner("h", 0.5)
    payment = Transaction((OutPoint("abc", 0),), (TxOutput("bob", 5),))
    miner.mempool.append(payment)
    block = miner.build_block(1)
    assert block.txs[1:] == (payment,)
    assert len(block.txs) == 2


def test_found_block_is_broadcast_immediately_and_added_to_own_chain():
    miner = HonestMiner("h", 0.5)
    block = miner.build_block(1)
    assert miner.on_block_found(block) == [Broadcast(block)]
    assert miner.chain.tip == block


def test_included_mempool_transactions_are_removed():
    miner = HonestMiner("h", 0.5)
    payment = Transaction((OutPoint("abc", 0),), (TxOutput("bob", 5),))
    miner.mempool.append(payment)
    miner.on_block_found(miner.build_block(1))
    assert miner.mempool == []


def test_transactions_confirmed_elsewhere_leave_the_mempool():
    miner = HonestMiner("h", 0.5)
    payment = Transaction((OutPoint("abc", 0),), (TxOutput("bob", 5),))
    miner.mempool.append(payment)
    other = HonestMiner("o", 0.5)
    other.mempool.append(payment)
    miner.receive_block(other.build_block(1))
    assert miner.mempool == []


def test_receive_block_reports_the_chain_result():
    miner = HonestMiner("h", 0.5)
    assert miner.receive_block(child(GENESIS)) is AddResult.ACCEPTED
    assert miner.receive_block(child(child(child(GENESIS)))) is AddResult.ORPHAN


def test_mines_on_the_longest_chain_it_knows():
    miner = HonestMiner("h", 0.5)
    a1 = child(GENESIS, "a")
    b1 = child(GENESIS, "b")
    b2 = child(b1, "b")
    for block in (a1, b1, b2):
        miner.receive_block(block)
    assert miner.build_block(9).prev_hash == b2.hash


def test_block_arriving_before_its_parent_is_adopted_later():
    miner = HonestMiner("h", 0.5)
    first = child(GENESIS)
    second = child(first)
    third = child(second)
    assert miner.receive_block(third) is AddResult.ORPHAN
    assert miner.receive_block(second) is AddResult.ORPHAN
    assert miner.chain.tip == GENESIS
    assert miner.receive_block(first) is AddResult.ACCEPTED
    assert miner.chain.tip == third


def test_invalid_hash_share_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        HonestMiner("h", 1.5)
