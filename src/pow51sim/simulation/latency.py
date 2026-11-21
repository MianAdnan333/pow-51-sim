from dataclasses import dataclass
from random import Random
from typing import Protocol


class LatencyModel(Protocol):
    def sample(self, rng: Random) -> float: ...


@dataclass(frozen=True)
class FixedLatency:
    delay: float = 0.0

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError("delay must be non-negative")

    def sample(self, rng: Random) -> float:
        return self.delay


@dataclass(frozen=True)
class ExponentialLatency:
    mean: float

    def __post_init__(self) -> None:
        if self.mean <= 0:
            raise ValueError("mean must be positive")

    def sample(self, rng: Random) -> float:
        return rng.expovariate(1.0 / self.mean)
