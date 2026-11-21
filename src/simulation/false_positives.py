from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from defense.lpc import SafeModeStats, build_chain
from miners.honest import HonestMiner
from miners.miner import Miner
from miners.network import EventKind, Network
from simulation.seeding import derive_seed

BIG_MINER = "big"
COLUMNS = [
    "miner_share",
    "trial",
    "blocks_found",
    "flagged_blocks",
    "flagged",
    "flagged_rate",
]


class FalsePositiveExperiment:
    """Honest-only network: how often is a large honest miner flagged by the LPC rule?

    One honest miner holds `miner_share`; the rest is split among `other_miners`.
    There is no attacker, so every flagged block is a false positive. Flags are read
    from an observer node's Safe Mode stats.
    """

    def __init__(
        self,
        shares: Sequence[float] = (0.30, 0.35, 0.40, 0.45),
        trials: int = 100,
        seed: int = 0,
        blocks: int = 144,
        other_miners: int = 5,
        max_consecutive: int = 6,
    ) -> None:
        if trials < 1 or blocks < 1 or other_miners < 1 or not shares:
            raise ValueError("trials, blocks, other_miners and shares must be set")
        self.shares = list(shares)
        self.trials = trials
        self.seed = seed
        self.blocks = blocks
        self.other_miners = other_miners
        self.max_consecutive = max_consecutive

    def run(self) -> pd.DataFrame:
        rows = [
            self._run_trial(share, trial)
            for share in self.shares
            for trial in range(self.trials)
        ]
        frame: pd.DataFrame = pd.DataFrame(rows, columns=COLUMNS)
        return frame

    def run_to_csv(self, path: str | Path) -> pd.DataFrame:
        frame = self.run()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)
        return frame

    def _run_trial(self, share: float, trial: int) -> dict[str, object]:
        miners: list[Miner] = []
        stats: list[SafeModeStats] = []
        shares = [share] + [(1 - share) / self.other_miners] * self.other_miners
        for index, miner_share in enumerate(shares):
            chain, node_stats = build_chain(True, self.max_consecutive)
            name = BIG_MINER if index == 0 else f"other-{index}"
            miners.append(HonestMiner(name, miner_share, chain))
            stats.append(node_stats)
        seed = derive_seed(self.seed, share, self.max_consecutive, trial)
        network = Network(miners, seed=seed)
        network.run(max_blocks=self.blocks)
        network.settle()
        found = sum(
            e.kind is EventKind.BLOCK_FOUND and e.miner_id == BIG_MINER
            for e in network.log
        )
        flagged = sum(event.miner_id == BIG_MINER for event in stats[-1].events)
        return {
            "miner_share": share,
            "trial": trial,
            "blocks_found": found,
            "flagged_blocks": flagged,
            "flagged": flagged > 0,
            "flagged_rate": flagged / found if found else 0.0,
        }
