import pytest

from pow51sim.core.block import GENESIS
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.defense.confirmations import is_confirmed
from pow51sim.defense.rules import MaxReorgDepthRule, build_rules


def _chain_with_depth_limit(limit: int) -> Blockchain:
    chain = Blockchain(build_rules(limit))
    parent = GENESIS
    for t in range(1, 4):
        parent = parent.child("h", t)
        chain.add_block(parent)
    return chain


def _fork(chain: Blockchain, length: int) -> list:
    blocks, parent = [], GENESIS
    for t in range(1, length + 1):
        parent = parent.child("a", t)
        blocks.append(parent)
    return blocks


def test_depth_limit_rejects_deep_reorg():
    chain = _chain_with_depth_limit(2)
    *side, overtaking = _fork(chain, 4)
    for block in side:
        chain.add_block(block)
    with pytest.raises(InvalidBlockError):
        chain.add_block(overtaking)
    assert chain.tip.miner_id == "h"


def test_depth_limit_allows_reorg_within_limit():
    chain = _chain_with_depth_limit(3)
    for block in _fork(chain, 4):
        chain.add_block(block)
    assert chain.tip.miner_id == "a"


def test_build_rules_adds_depth_rule_only_when_limited():
    assert not any(isinstance(r, MaxReorgDepthRule) for r in build_rules(None))
    assert any(isinstance(r, MaxReorgDepthRule) for r in build_rules(5))


def test_is_confirmed_counts_blocks_above_payment():
    chain = _chain_with_depth_limit(10)
    assert is_confirmed(chain, payment_height=0, required=3)
    assert not is_confirmed(chain, payment_height=0, required=4)
