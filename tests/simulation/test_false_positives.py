import pandas as pd
import pytest

from simulation.false_positives import COLUMNS, FalsePositiveExperiment


def _run(**overrides) -> pd.DataFrame:
    params = {"shares": (0.3, 0.45), "trials": 20, "seed": 1}
    return FalsePositiveExperiment(**{**params, **overrides}).run()


def test_one_row_per_trial_with_expected_columns():
    frame = _run(trials=5)
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 10
    assert set(frame["miner_share"]) == {0.3, 0.45}


def test_default_shares_cover_thirty_to_forty_five_percent():
    assert FalsePositiveExperiment(trials=1).shares == [0.30, 0.35, 0.40, 0.45]


def test_same_seed_reproduces_results():
    pd.testing.assert_frame_equal(_run(), _run())


def test_larger_honest_miners_are_flagged_more_often():
    frame = _run(trials=60)
    rates = frame.groupby("miner_share")["flagged_blocks"].mean()
    assert rates[0.45] > rates[0.3]


def test_flags_never_exceed_the_blocks_the_miner_found():
    frame = _run()
    assert (frame["flagged_blocks"] <= frame["blocks_found"]).all()
    assert frame["flagged_rate"].between(0, 1).all()
    assert (frame["flagged"] == (frame["flagged_blocks"] > 0)).all()


def test_a_higher_threshold_flags_less():
    low = _run(shares=(0.45,), trials=40, max_consecutive=4)["flagged_blocks"].mean()
    high = _run(shares=(0.45,), trials=40, max_consecutive=8)["flagged_blocks"].mean()
    assert high < low


def test_run_to_csv_writes_the_file(tmp_path):
    path = tmp_path / "fp" / "fp.csv"
    frame = FalsePositiveExperiment(shares=(0.3,), trials=2).run_to_csv(path)
    assert len(pd.read_csv(path)) == len(frame)


@pytest.mark.parametrize("bad", [{"trials": 0}, {"blocks": 0}, {"shares": []}])
def test_invalid_parameters_rejected(bad):
    with pytest.raises(ValueError):
        FalsePositiveExperiment(**bad)
