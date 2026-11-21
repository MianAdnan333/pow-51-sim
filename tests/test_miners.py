from random import Random

import pytest

from pow51sim.core.block import GENESIS
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.rules import default_rules
from pow51sim.defense.rules import LongPrivateChainRule
from pow51sim.miners.honest import HonestMiner
from pow51sim.miners.malicious import MaliciousMiner
from pow51sim.miners.receiver import BlockReceiver
from pow51sim.miners.selection import pick_winner


@pytest.mark.parametrize("share", [-0.1, 1.1])
def test_hash_power_must_be_a_fraction(share):
    with pytest.raises(ValueError):
        HonestMiner("h", share, Blockchain())


@pytest.mark.parametrize("share", [0.1, 0.35, 0.6])
def test_configurable_hash_power_share(share):
    assert HonestMiner("h", share, Blockchain()).hash_power == share
    assert MaliciousMiner("m", share, Blockchain()).hash_power == share


def test_honest_miner_extends_and_broadcasts():
    chain = Blockchain()
    miner = HonestMiner("h", 1.0, chain)
    broadcast = miner.mine(1)
    assert chain.height == 1
    assert broadcast == [chain.tip]


def test_honest_miner_adopts_received_blocks_without_rebroadcast():
    miner = HonestMiner("h", 0.5, Blockchain())
    block = GENESIS.child("other", 1)
    assert miner.receive(block) == []
    assert miner.chain.tip == block


def test_receiver_buffers_blocks_that_arrive_before_parent():
    chain = Blockchain()
    receiver = BlockReceiver(chain)
    first = GENESIS.child("a", 1)
    second = first.child("a", 2)
    receiver.submit(second)
    assert chain.height == 0
    receiver.submit(first)
    assert chain.tip == second


def test_receiver_drops_invalid_blocks():
    chain = Blockchain()
    receiver = BlockReceiver(chain)
    bad_timestamp = GENESIS.child("a", 5).child("a", 1)
    receiver.submit(GENESIS.child("a", 5))
    receiver.submit(bad_timestamp)
    assert chain.height == 1


def test_malicious_miner_withholds_until_it_overtakes_confirmed_chain():
    public = Blockchain()
    miner = MaliciousMiner("m", 0.4, public, confirmations=1)
    assert miner.mine(1) == []
    assert public.height == 0
    honest_block = GENESIS.child("h", 1)
    assert miner.receive(honest_block) == []
    released = miner.mine(2)
    assert [b.miner_id for b in released] == ["m", "m"]
    assert miner.released


def test_malicious_miner_can_release_on_receiving_an_honest_block():
    public = Blockchain()
    miner = MaliciousMiner("m", 0.4, public, confirmations=1)
    miner.mine(1)
    miner.mine(2)
    assert miner.released is False
    released = miner.receive(GENESIS.child("h", 1))
    assert len(released) == 2


def test_malicious_miner_acts_honestly_after_release():
    miner = MaliciousMiner("m", 0.6, Blockchain(), confirmations=0)
    assert len(miner.mine(1)) == 1
    follow_up = miner.mine(2)
    assert follow_up == [miner.chain.tip]


def test_malicious_lead_is_measured_against_public_view():
    public = Blockchain()
    miner = MaliciousMiner("m", 0.4, public, confirmations=5)
    miner.mine(1)
    assert miner.lead_over(public) == 1


def test_miner_discards_block_its_own_chain_rejects():
    chain = Blockchain([*default_rules(), LongPrivateChainRule(3)])
    miner = HonestMiner("h", 1.0, chain)
    results = [miner.mine(t) for t in (1, 2, 3)]
    assert [len(r) for r in results] == [1, 1, 0]
    assert miner.last_mined is None
    assert chain.height == 2


def test_malicious_private_chain_ignores_honest_network_defenses():
    public = Blockchain([*default_rules(), LongPrivateChainRule(3)])
    miner = MaliciousMiner("m", 0.4, public, confirmations=99)
    for t in range(1, 6):
        miner.mine(t)
    assert miner.chain.height == 5
    assert miner.last_mined is not None


def test_pick_winner_ignores_zero_hash_power():
    public = Blockchain()
    miners = [HonestMiner("h", 0.0, public), HonestMiner("g", 1.0, public)]
    winners = {pick_winner(miners, Random(i)).miner_id for i in range(20)}
    assert winners == {"g"}
