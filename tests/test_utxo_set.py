import pytest

from pow51sim.core.block import GENESIS
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.core.rules import UtxoRule, default_rules
from pow51sim.core.transaction import OutPoint, Transaction, TxOutput
from pow51sim.core.utxo import UTXOSet

from .helpers import extend, funding_block, spend


def test_apply_block_adds_outputs():
    block, [coin] = funding_block(50)
    utxos = UTXOSet()
    utxos.apply_block(block)
    assert coin in utxos
    assert utxos.get(coin) == TxOutput("alice", 50)
    assert utxos.balance("alice") == 50


def test_spend_consumes_input_and_creates_output():
    funding, [coin] = funding_block(50)
    payment = spend(coin, "bob")
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(extend(funding, "m", (payment,))[0])
    assert coin not in utxos
    assert utxos.balance("alice") == 0
    assert utxos.balance("bob") == 50


def test_missing_input_is_rejected_and_changes_nothing():
    funding, [coin] = funding_block(50)
    good = spend(coin, "bob")
    ghost = Transaction((OutPoint("nope", 0),), (TxOutput("eve", 1),))
    utxos = UTXOSet()
    utxos.apply_block(funding)
    bad_block = extend(funding, "m", (good, ghost))[0]
    with pytest.raises(InvalidBlockError):
        utxos.apply_block(bad_block)
    assert utxos.balance("alice") == 50
    assert len(utxos) == 1


def test_rollback_restores_previous_state():
    funding, [coin] = funding_block(50)
    spending = extend(funding, "m", (spend(coin, "bob"),))[0]
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(spending)
    utxos.rollback_block(spending)
    assert utxos.balance("alice") == 50
    assert utxos.balance("bob") == 0


def test_rollback_handles_output_created_and_spent_in_same_block():
    funding, [coin] = funding_block(50)
    first = spend(coin, "bob")
    second = spend(OutPoint(first.tx_id, 0), "carol")
    block = extend(funding, "m", (first, second))[0]
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(block)
    assert utxos.balance("carol") == 50
    utxos.rollback_block(block)
    assert utxos.balance("alice") == 50
    assert len(utxos) == 1


def test_rollback_of_unapplied_block_is_an_error():
    block, _ = funding_block(50)
    with pytest.raises(ValueError):
        UTXOSet().rollback_block(block)


def _chain_with_utxos() -> tuple[Blockchain, UTXOSet]:
    chain = Blockchain([*default_rules(), UtxoRule()])
    return chain, UTXOSet.for_chain(chain)


def test_updates_as_blocks_are_added_to_the_chain():
    chain, utxos = _chain_with_utxos()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    assert utxos.balance("alice") == 50
    chain.add_block(extend(funding, "m", (spend(coin, "bob"),))[0])
    assert utxos.balance("bob") == 50


def test_rolls_back_on_reorg_to_a_conflicting_fork():
    chain, utxos = _chain_with_utxos()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    payment = spend(coin, "victim")
    for block in extend(funding, "honest", (payment,), ()):
        chain.add_block(block)
    assert utxos.balance("victim") == 50

    refund = spend(coin, "alice", nonce=1)
    for block in extend(funding, "attacker", (refund,), (), ()):
        chain.add_block(block)

    assert utxos.balance("victim") == 0
    assert utxos.balance("alice") == 50
    assert OutPoint(payment.tx_id, 0) not in utxos
    assert OutPoint(refund.tx_id, 0) in utxos


def test_side_fork_leaves_utxo_set_untouched():
    chain, utxos = _chain_with_utxos()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    for block in extend(funding, "honest", (spend(coin, "bob"),), ()):
        chain.add_block(block)
    chain.add_block(extend(funding, "other", (spend(coin, "carol", nonce=1),))[0])
    assert utxos.balance("bob") == 50
    assert utxos.balance("carol") == 0


def test_failed_reorg_is_atomic():
    chain = Blockchain()
    utxos = UTXOSet.for_chain(chain)
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    chain.add_block(extend(funding, "honest", (spend(coin, "bob"),))[0])
    ghost = Transaction((OutPoint("nope", 0),), (TxOutput("eve", 1),))
    fork_a, fork_b = extend(funding, "attacker", (), (ghost,))
    chain.add_block(fork_a)
    with pytest.raises(InvalidBlockError):
        chain.add_block(fork_b)
    assert utxos.balance("bob") == 50
    assert chain.height == 2
    assert fork_b.hash not in chain


def test_for_chain_builds_state_from_existing_blocks():
    chain = Blockchain()
    funding, _ = funding_block(50)
    chain.add_block(funding)
    assert UTXOSet.for_chain(chain).balance("alice") == 50
    assert GENESIS.hash in chain
