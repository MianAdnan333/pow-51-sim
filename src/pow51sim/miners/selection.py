from collections.abc import Sequence
from typing import Protocol

from pow51sim.miners.base import Miner


class Chooser(Protocol):
    def choices(
        self, population: Sequence[Miner], weights: Sequence[float]
    ) -> list[Miner]: ...


def pick_winner(miners: Sequence[Miner], chooser: Chooser) -> Miner:
    weights = [miner.hash_power for miner in miners]
    return chooser.choices(miners, weights)[0]
