import numpy as np
import pandas as pd
import pytest

from dashboard.engine import (
    COLUMNS,
    SimParams,
    honest_limit_probability,
    race_trace,
    run_grid,
)

SHARES = (0.2, 0.55)
PARAMS = SimParams(trials=60, confirmations=3, lpc_limit=6, seed=7)


def _grid(defense: bool, params: SimParams = PARAMS, shares=SHARES) -> pd.DataFrame:
    return run_grid(shares, params, defense)


def _deterministic(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(columns="runtime_ms")


def test_grid_has_the_columns_the_dashboard_expects():
    frame = _grid(False)
    assert list(frame.columns) == COLUMNS
    assert COLUMNS == [
        "scenario",
        "attacker_share",
        "attack_success",
        "blocked_by_safe_mode",
        "private_len",
        "reorg_depth",
        "runtime_ms",
    ]
    assert len(frame) == PARAMS.trials * len(SHARES)
    assert frame["attack_success"].dtype == bool
    assert (frame["runtime_ms"] > 0).all()


def test_scenario_labels_match_the_dashboard():
    assert set(_grid(False)["scenario"]) == {"Defense OFF"}
    assert set(_grid(True)["scenario"]) == {"Defense ON"}


def test_same_seed_reproduces_results():
    for defense in (False, True):
        pd.testing.assert_frame_equal(
            _deterministic(_grid(defense)), _deterministic(_grid(defense))
        )


def test_different_seeds_give_different_results():
    other = SimParams(trials=60, seed=8)
    assert not _deterministic(_grid(False)).equals(_deterministic(_grid(False, other)))


def test_results_do_not_depend_on_which_other_shares_are_requested():
    alone = _grid(False, shares=(0.55,))
    together = _grid(False)
    rows = together[together["attacker_share"] == 0.55].reset_index(drop=True)
    pd.testing.assert_frame_equal(_deterministic(alone), _deterministic(rows))


def test_defense_never_increases_success():
    off, on = _grid(False), _grid(True)
    assert (on["attack_success"].to_numpy() <= off["attack_success"].to_numpy()).all()


def test_every_prevented_attack_is_flagged_as_blocked():
    params = SimParams(trials=80, confirmations=6, lpc_limit=6, seed=3)
    off, on = _grid(False, params, (0.55,)), _grid(True, params, (0.55,))
    prevented = off["attack_success"].to_numpy() & ~on["attack_success"].to_numpy()
    assert prevented.any()
    assert (prevented == on["blocked_by_safe_mode"].to_numpy()).all()
    assert not off["blocked_by_safe_mode"].any()


def test_success_rises_with_attacker_share():
    params = SimParams(trials=100, confirmations=1, seed=5)
    rates = (
        _grid(False, params, (0.1, 0.3, 0.55))
        .groupby("attacker_share")["attack_success"]
        .mean()
    )
    assert rates.is_monotonic_increasing


def test_a_failed_attack_reorgs_nothing():
    frame = _grid(True)
    assert (frame[~frame["attack_success"]]["reorg_depth"] == 0).all()


def test_limit_just_above_the_confirmation_depth_stops_every_attack():
    params = SimParams(trials=80, confirmations=3, lpc_limit=4, seed=7)
    assert not _grid(True, params, (0.55,))["attack_success"].any()
    assert _grid(False, params, (0.55,))["attack_success"].any()


def test_extreme_shares():
    params = SimParams(trials=10, confirmations=0)
    assert run_grid([1.0], params, False)["attack_success"].all()
    assert not run_grid([0.0], params, False)["attack_success"].any()


@pytest.mark.parametrize(
    "bad",
    [
        lambda: run_grid([], PARAMS, False),
        lambda: run_grid([1.5], PARAMS, False),
        lambda: SimParams(trials=0),
        lambda: SimParams(lpc_limit=1),
        lambda: SimParams(confirmations=-1),
        lambda: honest_limit_probability([0.3], limit=1),
    ],
)
def test_invalid_input_rejected(bad):
    with pytest.raises(ValueError):
        bad()


@pytest.mark.parametrize("defense", [False, True])
def test_the_fast_replay_model_tracks_the_real_simulator(defense):
    params = SimParams(trials=150, confirmations=3, lpc_limit=6, seed=1)
    real = _grid(defense, params, (0.5,))["attack_success"].mean()
    model = np.mean([race_trace(0.5, params, defense, s).accepted for s in range(300)])
    assert model == pytest.approx(real, abs=0.2)


def test_race_trace_is_reproducible_and_well_formed():
    first = race_trace(0.45, PARAMS, True, seed=3)
    assert first == race_trace(0.45, PARAMS, True, seed=3)
    assert set(first.events) <= {"H", "A"}
    assert first.events.count("H") == first.honest_blocks
    assert first.events.count("A") == first.private_blocks


def test_same_seed_replays_the_same_blocks_with_and_without_defense():
    for seed in range(10):
        off = race_trace(0.5, PARAMS, False, seed)
        on = race_trace(0.5, PARAMS, True, seed)
        assert off.events == on.events
        assert on.accepted <= off.accepted


def test_a_blocked_trace_explains_itself():
    blocked = next(
        trace
        for seed in range(200)
        if (trace := race_trace(0.55, PARAMS, True, seed)).blocked_by_safe_mode
    )
    assert not blocked.accepted
    assert blocked.accepted_private_blocks == PARAMS.lpc_limit - 1
    assert "Safe Mode" in blocked.reason


def test_race_trace_rejects_invalid_shares():
    with pytest.raises(ValueError):
        race_trace(1.5, PARAMS, False, 1)


def test_false_positive_probability_matches_exact_small_case():
    curve = honest_limit_probability([0.5], limit=2, blocks=3)
    assert curve["probability"].iloc[0] == pytest.approx(0.375)


def test_false_positive_rate_rises_with_hash_share():
    shares = [round(s, 2) for s in np.arange(0.05, 0.71, 0.05)]
    probability = honest_limit_probability(shares, limit=6)["probability"]
    assert probability.is_monotonic_increasing
    assert probability.iloc[-1] > probability.iloc[0]


def test_false_positive_rate_falls_with_a_higher_limit():
    low = honest_limit_probability([0.4], limit=4)["probability"].iloc[0]
    high = honest_limit_probability([0.4], limit=8)["probability"].iloc[0]
    assert high < low


def test_false_positive_probability_is_a_probability():
    curve = honest_limit_probability([0.0, 0.3, 1.0], limit=6)
    assert curve["probability"].between(0, 1).all()
    assert curve["probability"].iloc[0] == 0
    assert curve["probability"].iloc[-1] == pytest.approx(1.0)
