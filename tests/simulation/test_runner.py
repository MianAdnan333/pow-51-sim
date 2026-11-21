import math

import pandas as pd
import pytest

from simulation.runner import (
    COLUMNS,
    DEFAULT_OUTPUT,
    DETAIL_COLUMNS,
    SimulationRunner,
    main,
    scenario_label,
)
from simulation.seeding import derive_seed

SMALL = {"shares": (0.3, 0.55), "depths": (1, 3), "trials": 6}
DETERMINISTIC = [c for c in COLUMNS if c not in ("runtime_ms", "memory_mb")]


def _run(**overrides) -> pd.DataFrame:
    return SimulationRunner(**{**SMALL, "measure_memory": False, **overrides}).run()


def test_output_has_the_required_columns_in_order():
    assert list(_run().columns) == COLUMNS
    assert COLUMNS == [
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
        "runtime_ms",
        "memory_mb",
    ]


def test_one_row_per_trial_over_the_whole_grid():
    frame = _run()
    assert len(frame) == 2 * 2 * 2 * 6
    assert set(frame["scenario"]) == {"Defense OFF", "Defense ON"}
    assert set(frame["confirmation_depth"]) == {1, 3}
    assert set(frame["attacker_share"]) == {0.3, 0.55}
    assert scenario_label(True) == "Defense ON"
    assert scenario_label(False) == "Defense OFF"


def test_same_seed_reproduces_results_and_other_seeds_differ():
    first, again = _run(seed=4), _run(seed=4)
    pd.testing.assert_frame_equal(first[DETERMINISTIC], again[DETERMINISTIC])
    assert not first[DETERMINISTIC].equals(_run(seed=5, trials=20)[DETERMINISTIC][:48])


def test_derived_seeds_are_stable_distinct_and_independent_of_the_defense_mode():
    assert derive_seed(1, 0.3, 3, 0) == derive_seed(1, 0.3, 3, 0)
    seeds = {derive_seed(1, share, 3, t) for share in (0.1, 0.2) for t in range(50)}
    assert len(seeds) == 100
    assert derive_seed(1, 0.3, 3, 0) != derive_seed(2, 0.3, 3, 0)


def test_defense_modes_are_paired_so_on_never_beats_off_per_trial():
    frame = _run(trials=15)
    keys = ["confirmation_depth", "attacker_share"]
    off = frame[frame["scenario"] == "Defense OFF"].reset_index(drop=True)
    on = frame[frame["scenario"] == "Defense ON"].reset_index(drop=True)
    assert (off[keys] == on[keys]).all().all()
    assert (on["attack_success"].to_numpy() <= off["attack_success"].to_numpy()).all()


def test_runtime_is_measured_and_memory_only_when_requested():
    without = _run()
    assert (without["runtime_ms"] > 0).all()
    assert without["memory_mb"].isna().all()
    with_memory = _run(measure_memory=True, trials=2, shares=(0.4,), depths=(1,))
    assert (with_memory["memory_mb"] > 0).all()
    assert not any(math.isnan(v) for v in with_memory["memory_mb"])


def test_detailed_mode_appends_block_ownership_columns():
    detailed = _run(detailed=True)
    assert list(detailed.columns) == COLUMNS + DETAIL_COLUMNS
    assert (detailed["attacker_blocks"] >= 0).all()
    assert list(_run().columns) == COLUMNS


def test_run_to_csv_creates_the_file_and_parent_folder(tmp_path):
    path = tmp_path / "nested" / "results.csv"
    frame = SimulationRunner(**SMALL, measure_memory=False).run_to_csv(path)
    saved = pd.read_csv(path)
    assert list(saved.columns) == COLUMNS
    assert len(saved) == len(frame)


def test_default_output_path():
    assert DEFAULT_OUTPUT.as_posix() == "results/results.csv"


def test_cli_writes_the_csv_with_trials_and_seed(tmp_path, capsys):
    out = tmp_path / "cli.csv"
    frame = main(["--trials", "2", "--seed", "3", "--out", str(out), "--no-memory"])
    assert out.exists()
    assert len(frame) == 6 * 3 * 2 * 2
    assert "wrote" in capsys.readouterr().out
    assert len(pd.read_csv(out)) == len(frame)


@pytest.mark.parametrize(
    "bad",
    [
        {"trials": 0},
        {"shares": ()},
        {"depths": ()},
        {"defense_modes": ()},
    ],
)
def test_invalid_configuration_rejected(bad):
    with pytest.raises(ValueError):
        SimulationRunner(**bad)
