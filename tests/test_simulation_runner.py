import pandas as pd
import pytest

from pow51sim.simulation.simulation_runner import (
    COLUMNS,
    DETAIL_COLUMNS,
    ParameterGrid,
    SimulationRunner,
    scenario_label,
)

SMALL_GRID = ParameterGrid(
    attacker_shares=(0.2, 0.6), confirmations=(1, 3), defense=(False, True)
)
DETERMINISTIC = [c for c in COLUMNS if c not in ("runtime_ms", "memory_mb")]


def _run(trials=5, seed=0, grid=SMALL_GRID) -> pd.DataFrame:
    return SimulationRunner(trials, seed=seed, grid=grid).run()


def test_default_grid_spans_ten_to_sixty_percent():
    grid = ParameterGrid()
    assert min(grid.attacker_shares) == 0.1
    assert max(grid.attacker_shares) == 0.6
    assert set(grid.defense) == {False, True}


def test_output_has_the_requested_columns_and_one_row_per_trial():
    frame = _run(trials=4)
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 4 * len(SMALL_GRID.cells())


def test_every_grid_cell_is_labelled():
    frame = _run(trials=2)
    expected = {scenario_label(c, d) for c in (1, 3) for d in (False, True)}
    assert set(frame["scenario"]) == expected
    assert set(frame["attacker_share"]) == {0.2, 0.6}


def test_same_seed_reproduces_results():
    first, second = _run(seed=3), _run(seed=3)
    pd.testing.assert_frame_equal(first[DETERMINISTIC], second[DETERMINISTIC])


def test_different_seeds_give_different_results():
    assert not _run(trials=20, seed=1)[DETERMINISTIC].equals(
        _run(trials=20, seed=2)[DETERMINISTIC]
    )


def test_runtime_and_memory_are_measured():
    frame = _run(trials=2)
    assert (frame["runtime_ms"] > 0).all()
    assert (frame["memory_mb"] > 0).all()


def test_detailed_mode_appends_structure_columns():
    detailed = SimulationRunner(2, grid=SMALL_GRID, detailed=True).run()
    assert list(detailed.columns) == COLUMNS + DETAIL_COLUMNS
    assert (detailed["orphaned_blocks"] <= detailed["total_blocks"]).all()
    assert list(_run(trials=2).columns) == COLUMNS


def test_defense_caps_runs_below_threshold_and_cuts_success():
    grid = ParameterGrid(attacker_shares=(0.45,), confirmations=(3,))
    frame = SimulationRunner(150, grid=grid).run()
    on = frame[frame["scenario"].str.endswith("on")]
    off = frame[frame["scenario"].str.endswith("off")]
    assert on["max_consecutive_by_one_miner"].max() < 6
    assert off["max_consecutive_by_one_miner"].max() >= 6
    assert on["attack_success"].mean() < off["attack_success"].mean()


def test_run_to_csv_writes_a_readable_file(tmp_path):
    path = tmp_path / "out" / "results.csv"
    frame = SimulationRunner(3, grid=SMALL_GRID).run_to_csv(path)
    saved = pd.read_csv(path)
    assert list(saved.columns) == COLUMNS
    assert len(saved) == len(frame)
    assert saved["attack_success"].dtype == bool


def test_requires_at_least_one_trial():
    with pytest.raises(ValueError):
        SimulationRunner(0)
