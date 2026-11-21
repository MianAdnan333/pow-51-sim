import time
import tracemalloc
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from random import Random

import pandas as pd

from pow51sim.defense.rules import build_rules
from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.output import save_frame
from pow51sim.simulation.scenario import AttackResult, AttackScenario

BYTES_PER_MB = 1024 * 1024

COLUMNS = [
    "scenario",
    "attacker_share",
    "attack_success",
    "final_chain_length",
    "reorg_depth",
    "max_consecutive_by_one_miner",
    "runtime_ms",
    "memory_mb",
]
DETAIL_COLUMNS = [
    "orphaned_blocks",
    "total_blocks",
    "attacker_blocks",
    "honest_blocks",
    "top_honest_blocks",
]


@dataclass(frozen=True)
class ParameterGrid:
    attacker_shares: Sequence[float] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    confirmations: Sequence[int] = (1, 3, 6)
    defense: Sequence[bool] = (False, True)

    def cells(self) -> list[tuple[int, bool, float]]:
        return list(product(self.confirmations, self.defense, self.attacker_shares))


def scenario_label(confirmations: int, defense: bool) -> str:
    return f"conf={confirmations},defense={'on' if defense else 'off'}"


class SimulationRunner:
    """Runs `trials` seeded attack trials for every cell of a parameter grid.

    Defense "on" installs LongPrivateChainRule(max_consecutive). Trial i of every cell
    uses seed `seed + i`, so cells are directly comparable. Each trial is replayed once
    under tracemalloc to measure peak memory without skewing its runtime.
    `detailed=True` appends chain-structure columns (orphans, block ownership).
    """

    def __init__(
        self,
        trials: int,
        seed: int = 0,
        grid: ParameterGrid | None = None,
        honest_miners: int = 10,
        max_consecutive: int = 6,
        detailed: bool = False,
    ) -> None:
        if trials < 1:
            raise ValueError("trials must be at least 1")
        self.trials = trials
        self.seed = seed
        self.grid = grid or ParameterGrid()
        self.honest_miners = honest_miners
        self.max_consecutive = max_consecutive
        self.columns = COLUMNS + DETAIL_COLUMNS if detailed else COLUMNS

    def run(self) -> pd.DataFrame:
        rows = [
            self._run_trial(confirmations, defense, share, trial)
            for confirmations, defense, share in self.grid.cells()
            for trial in range(self.trials)
        ]
        frame: pd.DataFrame = pd.DataFrame(rows, columns=self.columns)
        return frame

    def run_to_csv(self, path: str | Path) -> pd.DataFrame:
        frame = self.run()
        save_frame(frame, path)
        return frame

    def _run_trial(
        self, confirmations: int, defense: bool, share: float, trial: int
    ) -> dict[str, object]:
        play = self._player(confirmations, defense, share, self.seed + trial)
        started = time.perf_counter()
        result = play()
        runtime_ms = (time.perf_counter() - started) * 1000
        return {
            "scenario": scenario_label(confirmations, defense),
            "attacker_share": share,
            "attack_success": result.success,
            "final_chain_length": result.final_chain_length,
            "reorg_depth": result.reorg_depth,
            "max_consecutive_by_one_miner": result.max_consecutive_by_one_miner,
            "runtime_ms": runtime_ms,
            "memory_mb": _peak_memory_mb(play),
            "orphaned_blocks": result.orphaned_blocks,
            "total_blocks": result.total_blocks,
            "attacker_blocks": result.attacker_blocks,
            "honest_blocks": result.honest_blocks,
            "top_honest_blocks": result.top_honest_blocks,
        }

    def _player(
        self, confirmations: int, defense: bool, share: float, seed: int
    ) -> Callable[[], AttackResult]:
        config = AttackConfig(share, confirmations, honest_miners=self.honest_miners)
        limit = self.max_consecutive if defense else None

        def play() -> AttackResult:
            rules = build_rules(None, max_consecutive=limit)
            return AttackScenario(config, rules, Random(seed)).run()

        return play


def _peak_memory_mb(play: Callable[[], AttackResult]) -> float:
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    play()
    peak = tracemalloc.get_traced_memory()[1]
    if not already_tracing:
        tracemalloc.stop()
    return peak / BYTES_PER_MB
