from dataclasses import FrozenInstanceError, replace

import pytest

from core.transaction import OutPoint, Transaction, TxOutput, coinbase

BASE = Transaction((OutPoint("abc", 0),), (TxOutput("alice", 10),), nonce=1)


def test_tx_id_is_deterministic():
    twin = Transaction((OutPoint("abc", 0),), (TxOutput("alice", 10),), nonce=1)
    assert BASE.tx_id == twin.tx_id
    assert len(BASE.tx_id) == 64


@pytest.mark.parametrize(
    "variant",
    [
        replace(BASE, inputs=(OutPoint("abd", 0),)),
        replace(BASE, inputs=(OutPoint("abc", 1),)),
        replace(BASE, inputs=()),
        replace(BASE, outputs=(TxOutput("bob", 10),)),
        replace(BASE, outputs=(TxOutput("alice", 11),)),
        replace(BASE, outputs=(TxOutput("alice", 5), TxOutput("alice", 5))),
        replace(BASE, nonce=2),
    ],
)
def test_changing_any_field_changes_the_tx_id(variant):
    assert variant.tx_id != BASE.tx_id


def test_field_boundaries_cannot_collide():
    first = Transaction((), (TxOutput("a", 12),))
    second = Transaction((), (TxOutput("a1", 2),))
    assert first.tx_id != second.tx_id


def test_coinbase_has_no_inputs_and_pays_the_miner():
    tx = coinbase("miner", 50, height=3)
    assert tx.is_coinbase
    assert tx.inputs == ()
    assert tx.outputs == (TxOutput("miner", 50),)


def test_coinbase_ids_are_unique_per_height():
    ids = {coinbase("miner", 50, height).tx_id for height in range(20)}
    assert len(ids) == 20


def test_spending_transaction_is_not_a_coinbase():
    assert not BASE.is_coinbase


def test_transactions_are_immutable():
    with pytest.raises(FrozenInstanceError):
        BASE.nonce = 5  # type: ignore[misc]


@pytest.mark.parametrize("outputs", [(), (TxOutput("a", 0),), (TxOutput("a", -1),)])
def test_invalid_outputs_rejected(outputs):
    with pytest.raises(ValueError):
        Transaction((), outputs)
