import pytest

from core.block import Block
from core.transaction import OutPoint, Transaction, TxOutput
from miners.honest import HonestMiner
from miners.malicious import MaliciousMiner
from miners.miner import to_broadcasts
from miners.network import Network

from .helpers import all_blocks, child, found_events

GENESIS = Block.genesis()


def _miner_with_public_chain(length: int = 3) -> tuple[MaliciousMiner, list[Block]]:
    miner = MaliciousMiner("mal", 0.4)
    blocks = []
    parent = GENESIS
    for _ in range(length):
        parent = child(parent, "h")
        miner.receive_block(parent)
        blocks.append(parent)
    return miner, blocks


def test_fork_from_starts_the_private_branch_at_the_given_block():
    miner, blocks = _miner_with_public_chain()
    miner.fork_from(blocks[1].hash)
    assert miner.private_active
    assert miner.private.tip == blocks[1]
    assert miner.private.main_chain() == [GENESIS, blocks[0], blocks[1]]
    assert miner.chain.tip == blocks[2]


def test_fork_from_unknown_block_raises():
    miner, _ = _miner_with_public_chain()
    with pytest.raises(KeyError):
        miner.fork_from("missing")


def test_mine_private_extends_the_private_tip_only():
    miner, blocks = _miner_with_public_chain()
    miner.fork_from(blocks[0].hash)
    first = miner.mine_private(timestamp=50)
    second = miner.mine_private(timestamp=51)
    assert first.prev_hash == blocks[0].hash
    assert second.prev_hash == first.hash
    assert second.index == 3
    assert miner.private.tip == second
    assert miner.chain.tip == blocks[2]
    assert first.hash not in miner.chain


def test_mine_private_requires_a_fork():
    with pytest.raises(RuntimeError):
        MaliciousMiner("mal", 0.4).mine_private(1)


def test_should_release_needs_a_strictly_longer_private_chain():
    miner, blocks = _miner_with_public_chain()
    assert not miner.should_release(0)
    miner.fork_from(blocks[1].hash)
    miner.mine_private(1)
    assert miner.private.tip.index == 3
    assert not miner.should_release(4)
    assert not miner.should_release(3)
    assert miner.should_release(2)


def test_release_returns_exactly_the_private_blocks_and_merges_them():
    miner, blocks = _miner_with_public_chain()
    miner.fork_from(blocks[0].hash)
    mined = [miner.mine_private(t) for t in range(10, 14)]
    released = miner.release()
    assert released == mined
    assert not miner.private_active
    assert miner.chain.tip == mined[-1]
    assert miner.release() == []


def test_found_blocks_are_withheld_while_a_private_fork_is_active():
    miner, blocks = _miner_with_public_chain()
    miner.fork_from(blocks[-1].hash)
    block = miner.build_block(1)
    assert block.prev_hash == blocks[-1].hash
    assert miner.on_block_found(block) == []
    assert miner.private.tip == block
    assert block.hash not in miner.chain


def test_private_blocks_consume_the_mempool_transactions_they_include():
    miner, blocks = _miner_with_public_chain()
    payment = Transaction((OutPoint("abc", 0),), (TxOutput("bob", 5),))
    miner.mempool.append(payment)
    miner.fork_from(blocks[-1].hash)
    first = miner.mine_private(1)
    second = miner.build_block(2)
    assert payment in first.txs
    assert payment not in second.txs
    assert miner.mempool == []


def test_without_a_private_fork_it_mines_like_an_honest_miner():
    miner = MaliciousMiner("mal", 0.4)
    block = miner.build_block(1)
    broadcasts = miner.on_block_found(block)
    assert [b.block for b in broadcasts] == [block]
    assert miner.chain.tip == block


def test_private_chain_ignores_honest_blocks_arriving_meanwhile():
    miner, blocks = _miner_with_public_chain(1)
    miner.fork_from(blocks[0].hash)
    miner.receive_block(child(blocks[0], "h"))
    assert miner.private.tip == blocks[0]
    assert miner.chain.tip.index == 2


def _attack_network(seed: int = 3) -> tuple[Network, MaliciousMiner, list[HonestMiner]]:
    attacker = MaliciousMiner("mal", 0.4)
    honest = [HonestMiner(f"h{i}", 0.2) for i in range(3)]
    attacker.fork_from(attacker.chain.tip.hash)
    return Network([attacker, *honest], seed=seed, block_interval=10), attacker, honest


def test_private_blocks_never_reach_honest_nodes_until_release():
    network, attacker, honest = _attack_network()
    network.run(max_blocks=200)
    network.settle()
    private_found = [e for e in found_events(network) if e.miner_id == "mal"]
    assert private_found
    for node in honest:
        assert all(b.miner_id != "mal" for b in all_blocks(node.chain))


def test_release_publishes_the_private_chain_to_every_honest_node():
    network, attacker, honest = _attack_network()
    network.run(max_blocks=200)
    network.settle()
    released = attacker.release()
    assert released
    network.publish(attacker.miner_id, to_broadcasts(released))
    network.run(until_time=network.now + 10)
    for node in honest:
        assert all(block.hash in node.chain for block in released)
