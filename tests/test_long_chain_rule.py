import pytest

from pow51sim.core.block import GENESIS, Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.core.rules import UtxoRule, default_rules
from pow51sim.core.transaction import Transaction
from pow51sim.defense.rules import LongPrivateChainRule, build_rules

from .helpers import funding_block, spend


def _add(
    chain: Blockchain, parent: Block, miner: str, txs: tuple[Transaction, ...] = ()
) -> Block:
    block = parent.child(miner, parent.timestamp + 1, txs=txs)
    chain.add_block(block)
    return block


def _plain_chain_with_run(length: int, miner: str = "m") -> Blockchain:
    chain = Blockchain()
    parent = GENESIS
    for _ in range(length):
        parent = _add(chain, parent, miner)
    return chain


@pytest.mark.parametrize(
    ("consecutive", "rejected"), [(5, False), (6, True), (7, True)]
)
def test_threshold_boundary(consecutive, rejected):
    chain = _plain_chain_with_run(consecutive - 1)
    candidate = chain.tip.child("m", chain.tip.timestamp + 1)
    rule = LongPrivateChainRule(max_consecutive=6)

    if rejected:
        with pytest.raises(InvalidBlockError):
            rule.validate(candidate, chain)
    else:
        rule.validate(candidate, chain)
    assert rule.safe_mode_active(chain) is rejected


def test_chain_stops_growing_at_the_sixth_consecutive_block():
    rule = LongPrivateChainRule(6)
    chain = Blockchain([*default_rules(), rule])
    parent = GENESIS
    for _ in range(5):
        parent = _add(chain, parent, "m")
    sixth = parent.child("m", parent.timestamp + 1)
    with pytest.raises(InvalidBlockError):
        chain.add_block(sixth)
    assert chain.height == 5
    assert sixth.hash not in chain
    assert rule.safe_mode_active(chain)


def test_threshold_is_a_parameter():
    rule = LongPrivateChainRule(max_consecutive=3)
    chain = Blockchain([*default_rules(), rule])
    parent = _add(chain, _add(chain, GENESIS, "m"), "m")
    with pytest.raises(InvalidBlockError):
        chain.add_block(parent.child("m", parent.timestamp + 1))


def test_default_threshold_is_six():
    assert LongPrivateChainRule().max_consecutive == 6


def test_threshold_below_two_is_invalid():
    with pytest.raises(ValueError):
        LongPrivateChainRule(max_consecutive=1)


def test_other_miner_resets_the_run():
    chain = Blockchain([*default_rules(), LongPrivateChainRule(6)])
    parent = GENESIS
    for miner in ["m"] * 5 + ["n"] + ["m"] * 5:
        parent = _add(chain, parent, miner)
    assert chain.height == 11


def test_runs_are_counted_per_branch():
    chain = Blockchain([*default_rules(), LongPrivateChainRule(6)])
    for start in (1, 100):
        parent = GENESIS.child("m", start)
        chain.add_block(parent)
        for _ in range(4):
            parent = _add(chain, parent, "m")
    assert len(chain.tips()) == 2


def _chain_with_rule(trigger: bool):
    rule = LongPrivateChainRule(6)
    chain = Blockchain([*default_rules(), UtxoRule(), rule])
    funding, [coin, _] = funding_block(50, 30)
    chain.add_block(funding)
    parent = funding
    for miner in ["x"] * 5 if trigger else ["x", "y", "x", "y", "x"]:
        parent = _add(chain, parent, miner)
    if trigger:
        with pytest.raises(InvalidBlockError):
            chain.add_block(parent.child("x", parent.timestamp + 1))
    payment = spend(coin, "victim")
    base = parent
    tip = _add(chain, _add(chain, base, "h", (payment,)), "g")
    return chain, rule, base, coin, payment, tip


def _add_fork(chain: Blockchain, base: Block, plan: list) -> None:
    parent = base
    for miner, txs in plan:
        parent = _add(chain, parent, miner, txs)


def test_conflicting_reorg_is_accepted_before_safe_mode():
    chain, rule, base, coin, payment, _ = _chain_with_rule(trigger=False)
    refund = spend(coin, "alice", nonce=1)
    _add_fork(chain, base, [("a", (refund,)), ("b", ()), ("a", ())])
    assert not rule.safe_mode_active(chain)
    confirmed = {tx for b in chain.main_chain() for tx in b.txs}
    assert refund in confirmed
    assert payment not in confirmed


def test_conflicting_reorg_is_rejected_in_safe_mode():
    chain, rule, base, coin, payment, tip = _chain_with_rule(trigger=True)
    assert rule.safe_mode_active(chain)
    refund = spend(coin, "alice", nonce=1)
    with pytest.raises(InvalidBlockError):
        _add_fork(chain, base, [("a", (refund,)), ("b", ()), ("a", ())])
    assert chain.tip == tip
    assert payment in {tx for b in chain.main_chain() for tx in b.txs}


def test_clean_reorg_is_accepted_in_safe_mode():
    chain, rule, base, _, _, tip = _chain_with_rule(trigger=True)
    _add_fork(chain, base, [("c", ()), ("d", ()), ("c", ())])
    assert chain.tip != tip
    assert chain.height == tip.index + 1


def test_plain_extension_needs_no_comparison_in_safe_mode():
    chain, _, _, _, _, tip = _chain_with_rule(trigger=True)
    _add(chain, tip, "z")
    assert chain.height == tip.index + 1


def test_safe_mode_is_tracked_per_chain():
    rule = LongPrivateChainRule(6)
    triggered = Blockchain([*default_rules(), rule])
    other = Blockchain([*default_rules(), rule])
    parent = GENESIS
    for _ in range(5):
        parent = _add(triggered, parent, "m")
    with pytest.raises(InvalidBlockError):
        triggered.add_block(parent.child("m", parent.timestamp + 1))
    assert rule.safe_mode_active(triggered)
    assert not rule.safe_mode_active(other)


def test_build_rules_includes_rule_only_when_requested():
    assert not any(isinstance(r, LongPrivateChainRule) for r in build_rules(None))
    rules = build_rules(None, max_consecutive=4)
    assert any(isinstance(r, LongPrivateChainRule) for r in rules)
