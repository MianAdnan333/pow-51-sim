from random import Random

import pytest

from pow51sim.analysis.metrics import longest_run
from pow51sim.analysis.tables import load_results
from pow51sim.defense.rules import build_rules
from pow51sim.simulation.builders import build_network
from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.scenario import AttackScenario
from pow51sim.simulation.simulation_runner import ParameterGrid, SimulationRunner

pytestmark = pytest.mark.integration

THRESHOLD = 6
HONEST_MINERS = 10


def _attack_results(defense: bool, share: float, confirmations: int, trials: int):
    config = AttackConfig(share, confirmations, honest_miners=HONEST_MINERS)
    rules = build_rules(None, THRESHOLD if defense else None)
    return [AttackScenario(config, rules, Random(seed)).run() for seed in range(trials)]


def _success_rate(results) -> float:
    return sum(r.success for r in results) / len(results)


def test_grid_to_csv_to_analysis_shows_defense_lowers_success(tmp_path):
    path = tmp_path / "grid.csv"
    grid = ParameterGrid(
        attacker_shares=(0.3, 0.45, 0.6), confirmations=(3,), defense=(False, True)
    )
    SimulationRunner(150, seed=7, grid=grid, detailed=True).run_to_csv(path)

    data = load_results(path)
    rates = (
        data.groupby(["attacker_share", "defense"])["attack_success"]
        .mean()
        .unstack("defense")
    )

    assert len(data) == 150 * len(grid.cells())
    assert (rates[True] <= rates[False] + 0.05).all()
    assert rates.loc[0.45, True] < rates.loc[0.45, False]
    assert rates.loc[0.6, True] < rates.loc[0.6, False]
    assert rates[True].mean() < rates[False].mean() - 0.05


def test_defense_caps_attacker_blocks_on_the_final_chain_below_the_threshold():
    results = _attack_results(defense=True, share=0.45, confirmations=3, trials=300)
    winners = [r for r in results if r.success]
    assert winners
    assert all(r.attacker_blocks < THRESHOLD for r in winners)
    assert all(r.max_consecutive_by_one_miner < THRESHOLD for r in results)
    assert any(r.private_chain_length >= THRESHOLD for r in winners)


def test_attack_scenario_defense_lowers_success_with_paired_seeds():
    off = _attack_results(defense=False, share=0.45, confirmations=3, trials=300)
    on = _attack_results(defense=True, share=0.45, confirmations=3, trials=300)
    assert _success_rate(on) < _success_rate(off)
    assert max(r.max_consecutive_by_one_miner for r in off) >= THRESHOLD


def test_deep_confirmations_make_the_defense_decisive():
    off = _attack_results(defense=False, share=0.45, confirmations=6, trials=200)
    on = _attack_results(defense=True, share=0.45, confirmations=6, trials=200)
    assert _success_rate(off) > 0.2
    assert _success_rate(on) == 0


def _honest_runs_after_simulation(defense: bool, seed: int) -> list[int]:
    rules = build_rules(None, THRESHOLD if defense else None)
    net = build_network(
        0.6,
        HONEST_MINERS,
        block_interval=10,
        mean_latency=1,
        confirmations=2,
        seed=seed,
        rules=rules,
    )
    net.run(3_000)
    net.drain()
    honest = net.miners[1:]
    return [longest_run(node.chain.main_chain()[1:]) for node in honest]


def test_network_simulation_defense_stops_adoption_of_long_private_chains():
    seeds = range(6)
    off = [max(_honest_runs_after_simulation(False, s)) for s in seeds]
    on = [max(_honest_runs_after_simulation(True, s)) for s in seeds]
    assert sum(run >= THRESHOLD for run in off) > 0
    assert all(run < THRESHOLD for run in on)


def test_network_simulation_is_reproducible_end_to_end():
    first = _honest_runs_after_simulation(True, seed=3)
    second = _honest_runs_after_simulation(True, seed=3)
    assert first == second
