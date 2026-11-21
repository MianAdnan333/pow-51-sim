from collections.abc import Sequence

from pow51sim.core.block import Block


def longest_run(blocks: Sequence[Block]) -> int:
    """Longest streak of consecutive blocks mined by the same miner."""
    best = run = 0
    previous: str | None = None
    for block in blocks:
        run = run + 1 if block.miner_id == previous else 1
        previous = block.miner_id
        best = max(best, run)
    return best
