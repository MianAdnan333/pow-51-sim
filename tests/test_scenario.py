import pytest

from pow51sim.defense.rules import build_rules
from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.scenario import AttackScenario

OVERTAKE = ["honest", "honest", "malicious", "malicious", "malicious"]


class _AlwaysMalicious:
    def choices(self, population, weights):
        return [m for m in population if m.miner_id == "malicious"]


def _main_txs(scenario: AttackScenario) -> set:
    return {tx for block in scenario.public.main_chain() for tx in block.txs}


def _scenario(config, chooser, limit=None) -> AttackScenario:
    return AttackScenario(config, build_rules(limit), chooser)


def test_payment_and_refund_spend_the_same_coin_to_different_owners():
    scenario = _scenario(AttackConfig(0.4), _AlwaysMalicious())
    assert scenario.payment.inputs == scenario.refund.inputs
    assert scenario.payment.outputs[0].recipient == "victim"
    assert scenario.refund.outputs[0].recipient == "malicious"


def test_double_spend_replaces_payment_with_refund(scripted):
    scenario = _scenario(AttackConfig(0.4, confirmations=2), scripted(OVERTAKE))
    result = scenario.run()
    assert result.success
    assert result.reorg_depth == 2
    assert result.private_chain_length == 3
    assert scenario.refund in _main_txs(scenario)
    assert scenario.payment not in _main_txs(scenario)
    assert scenario.public.validate()


def test_result_reports_final_chain_length_and_longest_run(scripted):
    result = _scenario(AttackConfig(0.4, confirmations=2), scripted(OVERTAKE)).run()
    assert result.final_chain_length == 4
    assert result.max_consecutive_by_one_miner == 3


def test_result_reports_orphans_and_block_ownership(scripted):
    result = _scenario(AttackConfig(0.4, confirmations=2), scripted(OVERTAKE)).run()
    assert result.total_blocks == 5
    assert result.orphaned_blocks == 2
    assert result.attacker_blocks == 3
    assert result.honest_blocks == 0
    assert result.top_honest_blocks == 0


def test_honest_win_leaves_no_orphans(scripted):
    config = AttackConfig(0.4, confirmations=1, give_up_deficit=1)
    result = _scenario(config, scripted(["honest"] * 3)).run()
    assert result.orphaned_blocks == 0
    assert result.attacker_blocks == 0
    assert result.honest_blocks == result.total_blocks == result.rounds


def test_multiple_honest_miners_split_the_remaining_hash_power():
    scenario = _scenario(AttackConfig(0.4, honest_miners=3), _AlwaysMalicious())
    assert [m.miner_id for m in scenario.honest_miners] == [
        "honest-0",
        "honest-1",
        "honest-2",
    ]
    assert sum(m.hash_power for m in scenario.honest_miners) == pytest.approx(0.6)


def test_honest_block_discarded_by_defense_does_not_break_the_race(scripted):
    config = AttackConfig(0.4, confirmations=9, max_rounds=3)
    rules = build_rules(None, max_consecutive=3)
    result = AttackScenario(config, rules, scripted(["honest"] * 3)).run()
    assert result.final_chain_length == 3
    assert result.max_consecutive_by_one_miner == 2


def test_overwhelming_hash_power_wins_without_confirmations():
    result = _scenario(AttackConfig(1.0, confirmations=0), _AlwaysMalicious()).run()
    assert result.success
    assert result.rounds == 1
    assert result.reorg_depth == 0
    assert result.private_chain_length == 1


def test_payment_is_mined_into_first_honest_block(scripted):
    config = AttackConfig(0.4, confirmations=2, max_rounds=1)
    scenario = _scenario(config, scripted(["honest"]))
    result = scenario.run()
    assert not result.success
    assert scenario.payment in _main_txs(scenario)
    assert scenario.refund not in _main_txs(scenario)


def test_attacker_gives_up_when_far_behind(scripted):
    config = AttackConfig(0.4, confirmations=1, give_up_deficit=2)
    result = _scenario(config, scripted(["honest"] * 5)).run()
    assert not result.success
    assert result.rounds == 3
    assert result.private_chain_length == 0


def test_reorg_depth_limit_defeats_the_same_attack(scripted):
    config = AttackConfig(0.4, confirmations=2)
    scenario = _scenario(config, scripted(OVERTAKE), limit=1)
    result = scenario.run()
    assert not result.success
    assert result.reorg_depth == 0
    assert result.private_chain_length == 3
    assert scenario.payment in _main_txs(scenario)


def test_unfinished_race_is_a_failure(scripted):
    config = AttackConfig(0.4, confirmations=2, max_rounds=3)
    result = _scenario(config, scripted(["honest", "honest", "malicious"])).run()
    assert not result.success
    assert result.rounds == 3


def test_invalid_share_rejected():
    with pytest.raises(ValueError):
        AttackConfig(1.5)
