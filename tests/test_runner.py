from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.runner import run_trials, sweep


def test_run_trials_is_reproducible():
    config = AttackConfig(0.3, confirmations=2)
    assert run_trials(config, 50, seed=1) == run_trials(config, 50, seed=1)


def test_sweep_has_one_row_per_cell():
    frame = sweep([0.1, 0.3], [1, 3], trials=20, reorg_limits=(None, 2))
    assert len(frame) == 8
    assert {"attacker_share", "confirmations", "success_rate"} <= set(frame.columns)


def test_larger_share_succeeds_more_often():
    frame = sweep([0.1, 0.45], [2], trials=300)
    low, high = frame["success_rate"]
    assert high > low


def test_depth_limit_below_confirmations_stops_attack():
    frame = sweep([0.45], [4], trials=200, reorg_limits=(3,))
    assert frame["success_rate"].iloc[0] == 0
