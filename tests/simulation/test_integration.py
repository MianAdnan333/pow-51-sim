import pandas as pd
import pytest

from simulation.runner import SimulationRunner, main

pytestmark = pytest.mark.integration

SHARE = 0.55
DETERMINISTIC = [
    "scenario",
    "attacker_share",
    "confirmation_depth",
    "attack_success",
    "blocked_by_safe_mode",
    "private_len",
    "final_chain_length",
    "reorg_depth",
    "max_consecutive_by_one_miner",
    "orphan_rate",
]


def _grid(seed: int = 0, trials: int = 80) -> pd.DataFrame:
    runner = SimulationRunner(
        shares=(SHARE,),
        depths=(1, 3, 6),
        trials=trials,
        seed=seed,
        measure_memory=False,
    )
    return runner.run()


def _rate(frame: pd.DataFrame, scenario: str, depth: int | None = None) -> float:
    rows = frame[frame["scenario"] == scenario]
    if depth is not None:
        rows = rows[rows["confirmation_depth"] == depth]
    return float(rows["attack_success"].mean())


def test_defense_on_is_at_most_defense_off_at_55_percent_share():
    frame = _grid()
    assert _rate(frame, "Defense ON") <= _rate(frame, "Defense OFF")
    for depth in (1, 3, 6):
        assert _rate(frame, "Defense ON", depth) <= _rate(frame, "Defense OFF", depth)


def test_the_defense_actually_lowers_success_overall():
    frame = _grid()
    assert _rate(frame, "Defense ON") < _rate(frame, "Defense OFF") - 0.05
    assert _rate(frame, "Defense ON", 6) == 0
    assert _rate(frame, "Defense OFF", 6) > 0.5


def test_results_are_reproducible_with_the_same_seed():
    first, again = _grid(seed=11, trials=30), _grid(seed=11, trials=30)
    pd.testing.assert_frame_equal(first[DETERMINISTIC], again[DETERMINISTIC])


def test_a_different_seed_changes_the_results():
    assert not _grid(seed=1, trials=30)[DETERMINISTIC].equals(
        _grid(seed=2, trials=30)[DETERMINISTIC]
    )


def test_cli_to_csv_round_trip(tmp_path):
    out = tmp_path / "results.csv"
    main(["--trials", "3", "--seed", "5", "--out", str(out), "--no-memory"])
    saved = pd.read_csv(out)
    assert {"Defense OFF", "Defense ON"} == set(saved["scenario"])
    rates = saved.groupby("scenario")["attack_success"].mean()
    assert rates["Defense ON"] <= rates["Defense OFF"]
