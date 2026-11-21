import pytest

from core.blockchain import AddResult
from defense.lpc import LongPrivateChainRule, SafeModeStats, build_chain

from .helpers import GENESIS, add_run, block_on, funding_block, spend


def test_five_consecutive_blocks_do_not_trigger():
    chain, stats = build_chain(defense=True, max_consecutive=6)
    add_run(chain, GENESIS, ["m"] * 5)
    assert chain.tip.index == 5
    assert (stats.triggers, stats.rejections, stats.false_positives) == (0, 0, 0)


def test_six_consecutive_honest_blocks_trigger_a_false_positive_but_are_accepted():
    chain, stats = build_chain(defense=True, max_consecutive=6)
    add_run(chain, GENESIS, ["m"] * 6)
    assert chain.tip.index == 6
    assert (stats.triggers, stats.rejections, stats.false_positives) == (1, 0, 1)
    assert stats.events[0].miner_id == "m"
    assert stats.events[0].run_length == 6
    assert stats.events[0].height == 6


def test_seven_consecutive_honest_blocks_trigger_twice():
    chain, stats = build_chain(defense=True, max_consecutive=6)
    add_run(chain, GENESIS, ["m"] * 7)
    assert chain.tip.index == 7
    assert (stats.triggers, stats.rejections, stats.false_positives) == (2, 0, 2)
    assert [event.run_length for event in stats.events] == [6, 7]


def _chain_with_a_fraudulent_private_branch(private_run: int):
    chain, stats = build_chain(defense=True, max_consecutive=6)
    funding, [coin, _] = funding_block(50, 30)
    chain.add_block(funding)
    payment, refund = spend(coin, "victim"), spend(coin, "attacker")
    paid = block_on(funding, "h1", (payment,))
    chain.add_block(paid)
    add_run(chain, paid, ["h2", "h1"] * 4)
    parent = funding
    results = []
    for step in range(private_run):
        txs = (refund,) if step == 0 else ()
        parent = block_on(parent, "attacker", txs)
        results.append(chain.add_block(parent))
    return chain, stats, results


def test_a_fraudulent_chain_is_rejected_at_the_sixth_consecutive_block():
    chain, stats, results = _chain_with_a_fraudulent_private_branch(6)
    assert results[:5] == [AddResult.ACCEPTED] * 5
    assert results[5] is AddResult.REJECTED
    assert (stats.triggers, stats.rejections, stats.false_positives) == (1, 1, 0)


def test_blocks_built_on_a_rejected_block_are_orphans():
    chain, stats, results = _chain_with_a_fraudulent_private_branch(6)
    follow_up = block_on(block_on(chain.tip, "attacker"), "attacker")
    assert chain.add_block(follow_up) is AddResult.ORPHAN


def test_a_fraudulent_chain_within_the_limit_is_not_caught():
    chain, stats, results = _chain_with_a_fraudulent_private_branch(5)
    assert all(result is AddResult.ACCEPTED for result in results)
    assert stats.triggers == 0


def test_the_threshold_is_a_parameter():
    chain, stats = build_chain(defense=True, max_consecutive=3)
    add_run(chain, GENESIS, ["m"] * 2)
    assert stats.triggers == 0
    add_run(chain, chain.tip, ["m"])
    assert stats.triggers == 1


def test_another_miner_resets_the_run():
    chain, stats = build_chain(defense=True, max_consecutive=6)
    add_run(chain, GENESIS, ["m"] * 5 + ["n"] + ["m"] * 5)
    assert stats.triggers == 0


def test_runs_are_counted_per_branch():
    chain, stats = build_chain(defense=True, max_consecutive=6)
    add_run(chain, GENESIS, ["m"] * 5)
    other = block_on(GENESIS, "m", timestamp=100)
    chain.add_block(other)
    add_run(chain, other, ["m"] * 4)
    assert stats.triggers == 0


def test_defense_off_installs_no_rule():
    chain, stats = build_chain(defense=False)
    add_run(chain, GENESIS, ["m"] * 8)
    assert stats.triggers == 0
    assert chain.tip.index == 8


def test_rule_must_be_attached_before_it_triggers():
    rule = LongPrivateChainRule(max_consecutive=2)
    first = block_on(GENESIS, "m")
    with pytest.raises(RuntimeError):
        rule.validate(block_on(first, "m"), [GENESIS, first])


def test_threshold_below_two_is_invalid():
    with pytest.raises(ValueError):
        LongPrivateChainRule(max_consecutive=1)


def test_stats_can_be_shared_and_default_to_zero():
    shared = SafeModeStats()
    assert LongPrivateChainRule(stats=shared).stats is shared
    assert LongPrivateChainRule().stats == SafeModeStats()
