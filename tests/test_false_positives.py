import pandas as pd
import pytest

from pow51sim.analysis.theory import false_positive_rate
from pow51sim.simulation.false_positives import COLUMNS, FalsePositiveExperiment


def _run(**overrides) -> pd.DataFrame:
    params = {"trials": 3, "shares": (0.2, 0.5), "thresholds": (4, 6), "rounds": 300}
    return FalsePositiveExperiment(**{**params, **overrides}).run()


def test_one_row_per_trial_with_expected_columns():
    frame = _run()
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 3 * 2 * 2


def test_same_seed_reproduces_results():
    pd.testing.assert_frame_equal(_run(seed=5), _run(seed=5))


def test_simulation_matches_the_closed_form_rate():
    frame = FalsePositiveExperiment(
        trials=1, shares=(0.5,), thresholds=(4,), rounds=30_000
    ).run()
    assert frame["blocked_rate"].iloc[0] == pytest.approx(
        false_positive_rate(0.5, 4), abs=0.03
    )


def test_larger_share_is_blocked_more_often():
    frame = _run(trials=10, shares=(0.2, 0.6), thresholds=(4,))
    rates = frame.groupby("miner_share")["blocked_rate"].mean()
    assert rates[0.6] > rates[0.2]


def test_higher_threshold_blocks_less():
    frame = _run(trials=10, shares=(0.5,), thresholds=(4, 8), rounds=2000)
    rates = frame.groupby("threshold")["blocked_rate"].mean()
    assert rates[8] < rates[4]


def test_safe_mode_triggers_for_a_dominant_honest_miner():
    frame = _run(shares=(0.6,), thresholds=(4,), rounds=1000)
    assert frame["safe_mode_triggered"].all()


def test_small_miner_is_essentially_never_blocked():
    frame = _run(trials=5, shares=(0.1,), thresholds=(6,))
    assert (frame["blocks_blocked"] == 0).all()


def test_closed_form_rate():
    assert false_positive_rate(0.5, 4) == pytest.approx(0.125)


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        FalsePositiveExperiment(trials=0)
