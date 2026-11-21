import pytest

from miners.honest import HonestMiner
from miners.network import Network
from simulation.attack import AttackScenario, make_scenario

SEEDS = range(60)


def _run(share, depth, defense, seed, **options):
    return make_scenario(share, depth, defense, seed, **options).run()


def test_overwhelming_attacker_without_confirmations_double_spends_at_once():
    result = _run(1.0, 0, False, seed=1)
    assert result.attack_success
    assert result.released
    assert result.private_len == 1
    assert result.final_chain_length == 2
    assert result.reorg_depth == 0
    assert result.miner_block_counts == {"attacker": 1}
    assert result.orphan_rate == 0.0


def test_attacker_without_hash_power_gives_up_and_the_payment_stands():
    result = _run(0.0, 3, False, seed=1)
    assert not result.attack_success
    assert not result.released
    assert result.private_len == 0
    assert not result.blocked_by_safe_mode
    assert result.final_chain_length > 3


def test_run_ends_at_max_time_without_a_release():
    result = _run(0.45, 6, False, seed=1, max_time=1.0)
    assert not result.attack_success
    assert not result.released
    assert result.final_chain_length == 1


def test_a_strong_attacker_reorgs_the_payment_out():
    results = [_run(0.6, 3, False, seed) for seed in SEEDS]
    winners = [r for r in results if r.attack_success]
    assert len(winners) > len(results) * 0.8
    assert all(r.released and r.reorg_depth >= 1 for r in winners)
    assert all(r.miner_block_counts.get("attacker", 0) >= 1 for r in winners)


def test_same_seed_gives_the_same_result():
    assert _run(0.5, 3, True, seed=9) == _run(0.5, 3, True, seed=9)


def test_different_seeds_give_different_results():
    results = {repr(_run(0.5, 3, False, seed)) for seed in range(12)}
    assert len(results) > 1


def test_result_fields_are_consistent():
    for seed in SEEDS:
        result = _run(0.45, 3, True, seed)
        assert 0.0 <= result.orphan_rate <= 1.0
        assert result.max_consecutive_by_one_miner >= 1
        assert sum(result.miner_block_counts.values()) == result.final_chain_length - 1
        assert result.private_len >= 0


def test_defense_on_never_does_better_than_off_with_the_same_seed():
    for depth in (1, 3, 6):
        for seed in SEEDS:
            off = _run(0.55, depth, False, seed)
            on = _run(0.55, depth, True, seed)
            assert on.attack_success <= off.attack_success


def test_every_attack_the_defense_prevents_is_flagged_as_blocked():
    prevented = 0
    for seed in SEEDS:
        off = _run(0.55, 6, False, seed)
        on = _run(0.55, 6, True, seed)
        if off.attack_success and not on.attack_success:
            prevented += 1
            assert on.blocked_by_safe_mode
        if on.blocked_by_safe_mode:
            assert off.attack_success
            assert not on.attack_success
    assert prevented > 0


def test_defense_off_never_reports_a_block():
    assert not any(_run(0.55, 6, False, seed).blocked_by_safe_mode for seed in SEEDS)


def test_deep_confirmations_force_a_long_chain_the_defense_catches():
    on = [_run(0.5, 6, True, seed) for seed in SEEDS]
    off = [_run(0.5, 6, False, seed) for seed in SEEDS]
    assert any(r.attack_success for r in off)
    assert not any(r.attack_success for r in on)
    assert all(r.max_consecutive_by_one_miner < 6 for r in on)


def test_the_attacker_must_be_a_malicious_miner():
    network = Network([HonestMiner("a", 0.5), HonestMiner("b", 0.5)])
    with pytest.raises(TypeError):
        AttackScenario(network, "a", "b", 3, False, max_time=10.0)


def test_invalid_scenario_parameters_are_rejected():
    with pytest.raises(ValueError):
        make_scenario(0.3, 3, False, seed=1, honest_miners=0)
    with pytest.raises(ValueError):
        make_scenario(1.5, 3, False, seed=1)
