import matplotlib
import pytest

from pow51sim.miners.base import Miner

matplotlib.use("Agg")


class ScriptedChooser:
    """Picks winners by miner_id in a fixed order."""

    def __init__(self, winners: list[str]) -> None:
        self._winners = iter(winners)

    def choices(self, population: list[Miner], weights: list[float]) -> list[Miner]:
        winner = next(self._winners)
        return [m for m in population if m.miner_id == winner]


@pytest.fixture
def scripted() -> type[ScriptedChooser]:
    return ScriptedChooser
