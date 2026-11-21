from statistics import mean, pstdev

import pytest

from pow51sim.core.blockchain import Blockchain
from pow51sim.defense.rules import build_rules
from pow51sim.miners.honest import HonestMiner
from pow51sim.simulation.builders import build_network
from pow51sim.simulation.latency import FixedLatency
from pow51sim.simulation.network import Network


def _honest_network(shares, interval, latency=0.0, seed=0) -> Network:
    miners = [HonestMiner(f"h{i}", s, Blockchain()) for i, s in enumerate(shares)]
    return Network(miners, interval, FixedLatency(latency), seed)


def _snapshot(net: Network):
    return net.block_log, [m.chain.tip.hash for m in net.miners]


def test_same_seed_reproduces_the_simulation():
    runs = []
    for _ in range(2):
        net = build_network(0.3, 3, block_interval=10, mean_latency=1, seed=7)
        net.run(500)
        net.drain()
        runs.append(_snapshot(net))
    assert runs[0] == runs[1]


def test_different_seeds_diverge():
    logs = []
    for seed in (1, 2):
        net = build_network(0.3, 3, block_interval=10, mean_latency=1, seed=seed)
        net.run(500)
        logs.append(net.block_log)
    assert logs[0] != logs[1]


def test_block_arrival_times_are_exponential():
    net = _honest_network([1.0], interval=10.0, seed=3)
    net.run(20_000)
    times = [entry.time for entry in net.block_log]
    gaps = [b - a for a, b in zip([0.0, *times], times, strict=False)]
    assert mean(gaps) == pytest.approx(10.0, rel=0.1)
    assert pstdev(gaps) / mean(gaps) == pytest.approx(1.0, rel=0.1)


def test_block_production_follows_hash_power_share():
    net = _honest_network([0.7, 0.3], interval=10.0, seed=4)
    net.run(100_000)
    wins = sum(entry.miner_id == "h0" for entry in net.block_log)
    assert wins / len(net.block_log) == pytest.approx(0.7, abs=0.03)


def test_block_reaches_other_nodes_after_the_latency():
    net = _honest_network([0.5, 0.5], interval=1e9, latency=5.0, seed=1)
    while not net.block_log:
        net.step()
    found = net.block_log[0]
    finder = next(m for m in net.miners if m.miner_id == found.miner_id)
    other = next(m for m in net.miners if m is not finder)
    assert (finder.chain.height, other.chain.height) == (1, 0)
    while other.chain.height == 0:
        net.step()
    assert net.now - found.time == pytest.approx(5.0)


def test_every_block_reaches_every_honest_node():
    net = build_network(0.0, 4, block_interval=100, mean_latency=5, seed=2)
    net.run(20_000)
    net.drain()
    hashes = [entry.block_hash for entry in net.block_log]
    assert all(h in m.chain for m in net.miners for h in hashes)
    assert len({m.chain.height for m in net.miners}) == 1


def test_latency_creates_competing_forks():
    net = build_network(0.0, 5, block_interval=10, mean_latency=20, seed=5)
    net.run(5_000)
    net.drain()
    assert any(m.chain.fork_tips() for m in net.miners)


def test_malicious_fork_is_published_and_propagated():
    net = build_network(0.6, 3, 10, 1, confirmations=2, seed=1)
    net.run(2_000)
    net.drain()
    malicious, *honest = net.miners
    assert malicious.released
    mined = [e.block_hash for e in net.block_log if e.miner_id == "malicious"]
    assert all(h in node.chain for node in honest for h in mined)


def test_withheld_fork_never_reaches_honest_nodes():
    net = build_network(0.3, 3, 10, 1, confirmations=10_000, seed=1)
    net.run(3_000)
    net.drain()
    malicious, *honest = net.miners
    mined = [e.block_hash for e in net.block_log if e.miner_id == "malicious"]
    assert mined and not malicious.released
    assert not any(h in node.chain for node in honest for h in mined)


def _longest_run(blocks) -> int:
    best = run = 0
    previous = None
    for block in blocks[1:]:
        run = run + 1 if block.miner_id == previous else 1
        previous = block.miner_id
        best = max(best, run)
    return best


def test_honest_nodes_never_hold_a_run_beyond_the_rule_threshold():
    rules = build_rules(None, max_consecutive=3)
    net = build_network(0.6, 5, 10, 1, confirmations=2, seed=1, rules=rules)
    net.run(2_000)
    net.drain()
    honest = net.miners[1:]
    assert all(_longest_run(n.chain.main_chain()) < 3 for n in honest)


def test_drain_stops_mining_and_empties_queue():
    net = build_network(0.0, 2, block_interval=10, mean_latency=1, seed=0)
    net.run(100)
    net.drain()
    found = len(net.block_log)
    assert not net.step()
    assert len(net.block_log) == found


def test_run_advances_clock_to_requested_time():
    net = _honest_network([1.0], interval=10.0)
    net.run(50)
    assert net.now == 50


def test_rejects_shares_that_do_not_sum_to_one():
    with pytest.raises(ValueError):
        _honest_network([0.5, 0.3], interval=10.0)


def test_rejects_duplicate_miner_ids_and_bad_interval():
    twins = [HonestMiner("h", 0.5, Blockchain()), HonestMiner("h", 0.5, Blockchain())]
    with pytest.raises(ValueError):
        Network(twins, 10.0, FixedLatency())
    with pytest.raises(ValueError):
        _honest_network([1.0], interval=0)


def test_builder_requires_an_honest_node():
    with pytest.raises(ValueError):
        build_network(0.3, 0)
