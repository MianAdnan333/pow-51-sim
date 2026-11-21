import heapq
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from itertools import count

from core.block import Block
from miners.miner import Broadcast, Miner

SHARE_TOLERANCE = 1e-9


class EventKind(Enum):
    BLOCK_FOUND = "block_found"
    BLOCK_DELIVERED = "block_delivered"


@dataclass(frozen=True)
class Event:
    """`miner_id` is the finder for BLOCK_FOUND and the recipient for BLOCK_DELIVERED.
    A scheduled BLOCK_FOUND has no block yet; the processed event carries it."""

    time: float
    kind: EventKind
    miner_id: str
    block: Block | None = None


class Network:
    """Discrete-event simulation of block production and propagation.

    Blocks arrive as one Poisson process (exponential gaps, mean `block_interval`);
    the finder is drawn by hash share. The network never inspects miner strategy: it
    asks the finder what to broadcast and delivers it to every other node after
    `propagation_delay` plus up to `jitter` seconds.
    """

    def __init__(
        self,
        miners: Sequence[Miner],
        seed: int = 0,
        block_interval: float = 600.0,
        propagation_delay: float = 2.0,
        jitter: float = 0.0,
    ) -> None:
        self._validate(miners, block_interval, propagation_delay, jitter)
        self.miners = list(miners)
        self.block_interval = block_interval
        self.propagation_delay = propagation_delay
        self.jitter = jitter
        self.now = 0.0
        self.blocks_found = 0
        self.log: list[Event] = []
        self._by_id = {miner.miner_id: miner for miner in self.miners}
        self._rng = random.Random(seed)
        self._queue: list[tuple[float, int, Event]] = []
        self._order = count()
        self._schedule_next_block()

    def step(self) -> Event | None:
        if not self._queue:
            return None
        _, _, event = heapq.heappop(self._queue)
        self.now = event.time
        if event.kind is EventKind.BLOCK_FOUND:
            event = self._handle_found(event)
        else:
            self._handle_delivery(event)
        self.log.append(event)
        return event

    def run(
        self, until_time: float | None = None, max_blocks: int | None = None
    ) -> None:
        """Run until `until_time`, or until `max_blocks` blocks were found in total."""
        if until_time is None and max_blocks is None:
            raise ValueError("give until_time, max_blocks or both")
        while self._queue and not self._block_limit_reached(max_blocks):
            if until_time is not None and self._queue[0][0] > until_time:
                break
            self.step()
        if until_time is not None and not self._block_limit_reached(max_blocks):
            self.now = max(self.now, until_time)

    def settle(self) -> None:
        """Stop mining for good and deliver every block still in flight."""
        pending = [item for item in self._queue if self._is_delivery(item[2])]
        heapq.heapify(pending)
        self._queue = pending
        while self.step() is not None:
            pass

    def publish(self, sender_id: str, broadcasts: Sequence[Broadcast]) -> None:
        for broadcast in broadcasts:
            for node in self.miners:
                if node.miner_id != sender_id:
                    delay = self._delivery_delay(broadcast)
                    self._push(self._delivery(node, broadcast.block, delay))

    @staticmethod
    def _validate(
        miners: Sequence[Miner],
        block_interval: float,
        propagation_delay: float,
        jitter: float,
    ) -> None:
        if not miners:
            raise ValueError("at least one miner is required")
        if len({miner.miner_id for miner in miners}) != len(miners):
            raise ValueError("miner ids must be unique")
        total = sum(miner.hash_share for miner in miners)
        if not math.isclose(total, 1.0, abs_tol=SHARE_TOLERANCE):
            raise ValueError(f"hash shares must sum to 1.0, got {total}")
        if block_interval <= 0:
            raise ValueError("block_interval must be positive")
        if propagation_delay < 0 or jitter < 0:
            raise ValueError("propagation_delay and jitter must be non-negative")

    @staticmethod
    def _is_delivery(event: Event) -> bool:
        return event.kind is EventKind.BLOCK_DELIVERED

    def _block_limit_reached(self, max_blocks: int | None) -> bool:
        return max_blocks is not None and self.blocks_found >= max_blocks

    def _push(self, event: Event) -> None:
        heapq.heappush(self._queue, (event.time, next(self._order), event))

    def _schedule_next_block(self) -> None:
        gap = self._rng.expovariate(1.0 / self.block_interval)
        weights = [miner.hash_share for miner in self.miners]
        finder = self._rng.choices(self.miners, weights=weights)[0]
        self._push(Event(self.now + gap, EventKind.BLOCK_FOUND, finder.miner_id))

    def _handle_found(self, event: Event) -> Event:
        miner = self._by_id[event.miner_id]
        block = miner.build_block(int(self.now))
        self.blocks_found += 1
        self.publish(miner.miner_id, miner.on_block_found(block))
        self._schedule_next_block()
        return replace(event, block=block)

    def _handle_delivery(self, event: Event) -> None:
        if event.block is not None:
            self._by_id[event.miner_id].receive_block(event.block)

    def _delivery_delay(self, broadcast: Broadcast) -> float:
        if broadcast.delay is not None:
            return broadcast.delay
        extra = self._rng.uniform(0.0, self.jitter) if self.jitter else 0.0
        return self.propagation_delay + extra

    def _delivery(self, node: Miner, block: Block, delay: float) -> Event:
        return Event(self.now + delay, EventKind.BLOCK_DELIVERED, node.miner_id, block)
