from pow51sim.analysis.metrics import longest_run
from pow51sim.core.block import GENESIS


def _blocks(miners):
    parent, blocks = GENESIS, []
    for t, miner in enumerate(miners, start=1):
        parent = parent.child(miner, t)
        blocks.append(parent)
    return blocks


def test_longest_run_finds_the_longest_streak():
    assert longest_run(_blocks("aabbbab")) == 3


def test_longest_run_of_empty_and_single():
    assert longest_run([]) == 0
    assert longest_run(_blocks("a")) == 1
