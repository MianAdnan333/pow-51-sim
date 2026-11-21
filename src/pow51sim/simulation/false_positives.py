from collections.abc import Sequence
from pathlib import Path
from random import Random

import pandas as pd

from pow51sim.core.blockchain import Blockchain
from pow51sim.core.rules import default_rules
from pow51sim.defense.rules import LongPrivateChainRule
from pow51sim.miners.honest import HonestMiner
from pow51sim.miners.selection import pick_winner
from pow51sim.simulation.output import save_frame

COLUMNS = [
    "miner_share",
    "threshold",
    "blocks_found",
    "blocks_blocked",
    "blocked_rate",
    "safe_mode_triggered",
]


class FalsePositiveExperiment:
    """Honest-only network: how often is a big honest miner blocked by the run limit?

    One honest miner holds `miner_share` of the hash power; the rest is split evenly
    among `other_miners`. No attacker exists, so every rejection is a false positive.
    """

    def __init__(
        self,
        trials: int,
        seed: int = 0,
        shares: Sequence[float] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
        thresholds: Sequence[int] = (4, 6, 8),
        rounds: int = 1000,
        other_miners: int = 9,
    ) -> None:
        if trials < 1 or rounds < 1 or other_miners < 1:
            raise ValueError("trials, rounds and other_miners must be at least 1")
        self.trials = trials
        self.seed = seed
        self.shares = shares
        self.thresholds = thresholds
        self.rounds = rounds
        self.other_miners = other_miners

    def run(self) -> pd.DataFrame:
        rows = [
            self._run_trial(share, threshold, self.seed + trial)
            for threshold in self.thresholds
            for share in self.shares
            for trial in range(self.trials)
        ]
        frame: pd.DataFrame = pd.DataFrame(rows, columns=COLUMNS)
        return frame

    def run_to_csv(self, path: str | Path) -> pd.DataFrame:
        frame = self.run()
        save_frame(frame, path)
        return frame

    def _run_trial(self, share: float, threshold: int, seed: int) -> dict[str, object]:
        rule = LongPrivateChainRule(threshold)
        chain = Blockchain([*default_rules(), rule])
        big = HonestMiner("big", share, chain)
        others = [
            HonestMiner(f"other-{i}", (1 - share) / self.other_miners, chain)
            for i in range(self.other_miners)
        ]
        miners = [big, *others]
        rng = Random(seed)
        found = blocked = 0
        for round_no in range(1, self.rounds + 1):
            winner = pick_winner(miners, rng)
            mined = winner.mine(round_no)
            if winner is big:
                found += 1
                blocked += not mined
        return {
            "miner_share": share,
            "threshold": threshold,
            "blocks_found": found,
            "blocks_blocked": blocked,
            "blocked_rate": blocked / found if found else float("nan"),
            "safe_mode_triggered": rule.safe_mode_active(chain),
        }
