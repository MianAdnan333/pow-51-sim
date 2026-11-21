import argparse
import time
import tracemalloc
from collections.abc import Callable, Sequence
from pathlib import Path

import pandas as pd

from simulation.attack import ATTACKER_ID, AttackResult, make_scenario
from simulation.seeding import derive_seed

DEFAULT_SHARES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
DEFAULT_DEPTHS = (1, 3, 6)
DEFAULT_OUTPUT = Path("results/results.csv")
BYTES_PER_MB = 1024 * 1024

COLUMNS = [
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
DETAIL_COLUMNS = ["attacker_blocks", "honest_blocks", "top_honest_blocks"]


def scenario_label(defense: bool) -> str:
    return "Defense ON" if defense else "Defense OFF"


class SimulationRunner:
    """Runs `trials` seeded attacks for every (depth, defense mode, share) cell.

    Trial i of a cell uses the same derived seed with defense on and off, so the two
    modes see identical block arrivals and are directly comparable. Each trial is
    replayed once under tracemalloc for memory, so timing stays untraced.
    `detailed=True` appends block-ownership columns.
    """

    def __init__(
        self,
        shares: Sequence[float] = DEFAULT_SHARES,
        depths: Sequence[int] = DEFAULT_DEPTHS,
        defense_modes: Sequence[bool] = (False, True),
        trials: int = 100,
        seed: int = 0,
        honest_miners: int = 5,
        max_consecutive: int = 6,
        measure_memory: bool = True,
        detailed: bool = False,
    ) -> None:
        if trials < 1:
            raise ValueError("trials must be at least 1")
        if not shares or not depths or not defense_modes:
            raise ValueError("shares, depths and defense_modes must not be empty")
        self.shares = list(shares)
        self.depths = list(depths)
        self.defense_modes = list(defense_modes)
        self.trials = trials
        self.seed = seed
        self.honest_miners = honest_miners
        self.max_consecutive = max_consecutive
        self.measure_memory = measure_memory
        self.columns = COLUMNS + DETAIL_COLUMNS if detailed else COLUMNS

    def run(self) -> pd.DataFrame:
        rows = [
            self._run_trial(share, depth, defense, trial)
            for depth in self.depths
            for defense in self.defense_modes
            for share in self.shares
            for trial in range(self.trials)
        ]
        frame: pd.DataFrame = pd.DataFrame(rows, columns=self.columns)
        return frame

    def run_to_csv(self, path: str | Path = DEFAULT_OUTPUT) -> pd.DataFrame:
        frame = self.run()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)
        return frame

    def _run_trial(
        self, share: float, depth: int, defense: bool, trial: int
    ) -> dict[str, object]:
        seed = derive_seed(self.seed, share, depth, trial)

        def play() -> AttackResult:
            scenario = make_scenario(
                share,
                depth,
                defense,
                seed,
                honest_miners=self.honest_miners,
                max_consecutive=self.max_consecutive,
            )
            return scenario.run()

        started = time.perf_counter()
        result = play()
        runtime_ms = (time.perf_counter() - started) * 1000
        memory_mb = _peak_memory_mb(play) if self.measure_memory else float("nan")
        return _row(share, depth, defense, result, runtime_ms, memory_mb)


def _row(
    share: float,
    depth: int,
    defense: bool,
    result: AttackResult,
    runtime_ms: float,
    memory_mb: float,
) -> dict[str, object]:
    counts = result.miner_block_counts
    honest = [n for miner, n in counts.items() if miner != ATTACKER_ID]
    return {
        "scenario": scenario_label(defense),
        "attacker_share": share,
        "confirmation_depth": depth,
        "attack_success": result.attack_success,
        "blocked_by_safe_mode": result.blocked_by_safe_mode,
        "private_len": result.private_len,
        "final_chain_length": result.final_chain_length,
        "reorg_depth": result.reorg_depth,
        "max_consecutive_by_one_miner": result.max_consecutive_by_one_miner,
        "orphan_rate": result.orphan_rate,
        "runtime_ms": runtime_ms,
        "memory_mb": memory_mb,
        "attacker_blocks": counts.get(ATTACKER_ID, 0),
        "honest_blocks": sum(honest),
        "top_honest_blocks": max(honest, default=0),
    }


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


def main(argv: Sequence[str] | None = None) -> pd.DataFrame:
    parser = argparse.ArgumentParser(description="Run the 51% attack simulation grid.")
    parser.add_argument("--trials", type=int, default=100, help="trials per grid cell")
    parser.add_argument("--seed", type=int, default=0, help="base random seed")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="CSV path")
    parser.add_argument("--no-memory", action="store_true", help="skip memory tracing")
    parser.add_argument("--detailed", action="store_true", help="add block counts")
    args = parser.parse_args(argv)
    runner = SimulationRunner(
        trials=args.trials,
        seed=args.seed,
        measure_memory=not args.no_memory,
        detailed=args.detailed,
    )
    frame = runner.run_to_csv(args.out)
    rates = frame.groupby(["confirmation_depth", "scenario", "attacker_share"])[
        "attack_success"
    ].mean()
    print(f"wrote {len(frame)} trials to {args.out}")
    print(rates.unstack("attacker_share").round(2).to_string())
    return frame


if __name__ == "__main__":
    main()
