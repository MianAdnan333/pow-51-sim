"""Data source for the dashboard: the real simulator behind a small UI-facing API.

The UI calls `run_grid`, `race_trace`, `honest_limit_probability` and `SimParams`.
`run_grid` drives `SimulationRunner`; the single-race replay and the exact
false-positive curve come from the fast model in `dashboard.model`.
"""

from collections.abc import Sequence

import pandas as pd

from dashboard.model import (
    FALSE_POSITIVE_WINDOW,
    RaceTrace,
    SimParams,
    honest_limit_probability,
    race_trace,
)
from simulation.runner import SimulationRunner

COLUMNS = [
    "scenario",
    "attacker_share",
    "attack_success",
    "blocked_by_safe_mode",
    "private_len",
    "reorg_depth",
    "runtime_ms",
]

__all__ = [
    "COLUMNS",
    "FALSE_POSITIVE_WINDOW",
    "RaceTrace",
    "SimParams",
    "honest_limit_probability",
    "race_trace",
    "run_grid",
]


def run_grid(shares: Sequence[float], params: SimParams, defense: bool) -> pd.DataFrame:
    """One row per trial and share; scenario is "Defense OFF" or "Defense ON"."""
    runner = SimulationRunner(
        shares=shares,
        depths=(params.confirmations,),
        defense_modes=(defense,),
        trials=params.trials,
        seed=params.seed,
        max_consecutive=params.lpc_limit,
        measure_memory=False,
    )
    grid: pd.DataFrame = runner.run()[COLUMNS].reset_index(drop=True)
    return grid
