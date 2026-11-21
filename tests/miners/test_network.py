from statistics import mean

import pytest

from core.blockchain import Blockchain
from miners.honest import HonestMiner
from miners.miner import Broadcast
from miners.network import EventKind, Network

from .helpers import all_blocks, child, found_events, honest_network


def _run(seed: int, blocks: int = 300, shares=(0.5, 0.3, 0.2)) -> Network:
    network = honest_network(list(shares), seed=seed, block_interval=10)
    network.run(max_blocks=blocks)
    return network


def test_same_seed_gives_an_identical_event_log():
    assert _run(11).log == _run(11).log


def test_different_seeds_give_different_event_logs():
    assert _run(11).log != _run(12).log


@pytest.mark.parametrize(
    "shares", [(0.5, 0.4), (0.7, 0.7), (0.3, 0.3, 0.3), (1.0, 0.1)]
)
def test_hash_shares_must_sum_to_one(shares):
    with pytest.raises(ValueError):
        honest_network(list(shares))


def test_shares_summing_to_one_with_float_noise_are_accepted():
    honest_network([0.1] * 10)


def test_other_invalid_configuration_rejected():
    twins = [HonestMiner("h", 0.5), HonestMiner("h", 0.5)]
    with pytest.raises(ValueError):
        Network(twins)
    with pytest.raises(ValueError):
        Network([])
    with pytest.raises(ValueError):
        honest_network([1.0], block_interval=0)
    with pytest.raises(ValueError):
        honest_network([1.0], propagation_delay=-1)
    with pytest.raises(ValueError):
        honest_network([1.0], jitter=-1)


def test_win_fraction_matches_hash_share_over_10000_blocks():
    shares = (0.5, 0.3, 0.2)
    network = honest_network(list(shares), seed=1, block_interval=10)
    network.run(max_blocks=10_000)
    events = found_events(network)
    assert len(events) == 10_000
    for index, share in enumerate(shares):
        wins = sum(e.miner_id == f"h{index}" for e in events)
        assert wins / len(events) == pytest.approx(share, abs=0.02)


def test_zero_share_miner_never_wins():
    network = honest_network([1.0, 0.0], seed=2, block_interval=10)
    network.run(max_blocks=300)
    assert all(e.miner_id == "h0" for e in found_events(network))


@pytest.mark.parametrize("interval", [600.0, 10.0])
def test_mean_block_interval_matches_the_setting(interval):
    network = honest_network([0.5, 0.5], seed=4, block_interval=interval)
    network.run(max_blocks=10_000)
    times = [e.time for e in found_events(network)]
    gaps = [b - a for a, b in zip([0.0, *times], times, strict=False)]
    assert mean(gaps) == pytest.approx(interval, rel=0.05)


def test_found_block_reaches_every_other_node_after_the_delay():
    network = honest_network(
        [0.4, 0.3, 0.3], seed=5, block_interval=1e6, propagation_delay=2.0
    )
    first = None
    while first is None:
        event = network.step()
        assert event is not None
        first = event if event.kind is EventKind.BLOCK_FOUND else None
    assert first.block is not None
    finder = next(m for m in network.miners if m.miner_id == first.miner_id)
    others = [m for m in network.miners if m is not finder]
    assert finder.chain.tip == first.block
    assert all(first.block.hash not in m.chain for m in others)

    deliveries = []
    while len(deliveries) < len(others):
        event = network.step()
        assert event is not None
        deliveries.append(event)
    assert {e.miner_id for e in deliveries} == {m.miner_id for m in others}
    assert all(e.kind is EventKind.BLOCK_DELIVERED for e in deliveries)
    assert all(e.time == pytest.approx(first.time + 2.0) for e in deliveries)
    assert all(m.chain.tip == first.block for m in others)


def test_large_propagation_delay_causes_forks_and_orphans():
    network = honest_network(
        [0.25] * 4, seed=6, block_interval=10, propagation_delay=30.0
    )
    network.run(max_blocks=300)
    network.settle()
    assert any(len(m.chain.forks()) > 1 for m in network.miners)
    assert any(m.chain.orphaned_blocks() for m in network.miners)


def test_tiny_delay_keeps_forks_rare():
    network = honest_network(
        [0.25] * 4, seed=6, block_interval=600, propagation_delay=0.1
    )
    network.run(max_blocks=300)
    network.settle()
    orphans = sum(len(m.chain.orphaned_blocks()) for m in network.miners)
    assert orphans <= 3


def test_jittered_deliveries_still_converge_on_every_block():
    network = honest_network(
        [0.25] * 4, seed=7, block_interval=10, propagation_delay=1.0, jitter=60.0
    )
    network.run(max_blocks=200)
    network.settle()
    found = [e.block.hash for e in found_events(network) if e.block is not None]
    assert len(found) == 200
    for miner in network.miners:
        assert all(block_hash in miner.chain for block_hash in found)


def test_events_are_processed_in_time_order():
    network = _run(8, blocks=200)
    times = [event.time for event in network.log]
    assert times == sorted(times)
    assert network.now == times[-1]


def test_per_broadcast_delay_overrides_the_network_delay():
    network = honest_network([0.5, 0.5], seed=9, block_interval=1e9)
    block = child(network.miners[0].chain.tip)
    network.publish("h0", [Broadcast(block, delay=5.0)])
    event = network.step()
    assert event is not None
    assert event.kind is EventKind.BLOCK_DELIVERED
    assert event.miner_id == "h1"
    assert event.time == pytest.approx(5.0)


def test_run_needs_a_stop_condition_and_advances_the_clock():
    network = honest_network([1.0], block_interval=1e9)
    with pytest.raises(ValueError):
        network.run()
    network.run(until_time=50.0)
    assert network.now == 50.0
    assert network.log == []


def test_run_stops_after_max_blocks_in_total():
    network = honest_network([1.0], block_interval=10)
    network.run(max_blocks=5)
    assert network.blocks_found == 5
    network.run(max_blocks=5)
    assert network.blocks_found == 5
    network.run(max_blocks=8)
    assert network.blocks_found == 8


def test_step_returns_none_when_nothing_is_left():
    network = honest_network([1.0], block_interval=10)
    network.settle()
    assert network.step() is None


def test_settle_stops_mining_but_delivers_in_flight_blocks():
    network = honest_network([0.5, 0.5], seed=3, block_interval=10, propagation_delay=5)
    network.run(max_blocks=20)
    found = network.blocks_found
    network.settle()
    assert network.blocks_found == found
    assert len({m.chain.tip.index for m in network.miners}) == 1


def test_each_miner_keeps_its_own_chain_view():
    network = honest_network([0.5, 0.5], seed=3)
    chains = [m.chain for m in network.miners]
    assert all(isinstance(chain, Blockchain) for chain in chains)
    assert chains[0] is not chains[1]
    assert all_blocks(chains[0]) == all_blocks(chains[1])
