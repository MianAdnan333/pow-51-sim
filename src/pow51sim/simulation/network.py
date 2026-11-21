import heapq
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import count
from random import Random

from pow51sim.core.block import Block
from pow51sim.miners.base import Miner
from pow51sim.simulation.latency import LatencyModel

SHARE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class FoundBlock:
    time: float
    miner_id: str
    block_hash: str


class Network:
    """Discrete-event simulation of mining and block propagation.

    Each miner finds blocks as a Poisson process with rate hash_power / block_interval,
    so inter-arrival times are exponential. Blocks reach every other miner after an
    independently sampled latency (no relaying).
    """

    def __init__(
        self,
        miners: Sequence[Miner],
        block_interval: float,
        latency: LatencyModel,
        seed: int = 0,
    ) -> None:
        self._validate(miners, block_interval)
        self.miners = list(miners)
        self.block_interval = block_interval
        self.latency = latency
        self.now = 0.0
        self.block_log: list[FoundBlock] = []
        self._rng = Random(seed)
        self._queue: list[tuple[float, int, Callable[[], None]]] = []
        self._sequence = count()
        self._mining = True
        for miner in self.miners:
            self._schedule_mining(miner)

    def step(self) -> bool:
        if not self._queue:
            return False
        self.now, _, action = heapq.heappop(self._queue)
        action()
        return True

    def run(self, until: float) -> None:
        while self._queue and self._queue[0][0] <= until:
            self.step()
        self.now = until

    def drain(self) -> None:
        """Stop mining and deliver every block still in flight."""
        self._mining = False
        while self.step():
            pass

    @staticmethod
    def _validate(miners: Sequence[Miner], block_interval: float) -> None:
        if block_interval <= 0:
            raise ValueError("block_interval must be positive")
        if len({m.miner_id for m in miners}) != len(miners):
            raise ValueError("miner ids must be unique")
        if abs(sum(m.hash_power for m in miners) - 1.0) > SHARE_TOLERANCE:
            raise ValueError("hash power shares must sum to 1")

    def _at(self, time: float, action: Callable[[], None]) -> None:
        heapq.heappush(self._queue, (time, next(self._sequence), action))

    def _schedule_mining(self, miner: Miner) -> None:
        if miner.hash_power == 0:
            return
        rate = miner.hash_power / self.block_interval
        delay = self._rng.expovariate(rate)
        self._at(self.now + delay, lambda: self._on_found(miner))

    def _on_found(self, miner: Miner) -> None:
        if not self._mining:
            return
        broadcast = miner.mine(int(self.now))
        if miner.last_mined is not None:
            entry = FoundBlock(self.now, miner.miner_id, miner.last_mined.hash)
            self.block_log.append(entry)
        self._broadcast(miner, broadcast)
        self._schedule_mining(miner)

    def _broadcast(self, sender: Miner, blocks: list[Block]) -> None:
        for block in blocks:
            for node in self.miners:
                if node is not sender:
                    delay = self.latency.sample(self._rng)
                    self._at(self.now + delay, self._delivery(node, block))

    def _delivery(self, node: Miner, block: Block) -> Callable[[], None]:
        def deliver() -> None:
            self._broadcast(node, node.receive(block))

        return deliver
