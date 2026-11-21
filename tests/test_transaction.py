import pytest

from pow51sim.core.transaction import OutPoint, Transaction, TxOutput


def _coinbase(nonce: int = 0) -> Transaction:
    return Transaction((), (TxOutput("alice", 50),), nonce)


def test_coinbase_has_no_inputs():
    assert _coinbase().is_coinbase


def test_spend_is_not_coinbase():
    tx = Transaction((OutPoint("abc", 0),), (TxOutput("bob", 10),))
    assert not tx.is_coinbase


def test_tx_id_is_deterministic():
    assert _coinbase().tx_id == _coinbase().tx_id


def test_tx_id_changes_with_content():
    assert _coinbase(0).tx_id != _coinbase(1).tx_id


def test_total_out_sums_outputs():
    tx = Transaction((), (TxOutput("a", 3), TxOutput("b", 4)))
    assert tx.total_out == 7


def test_rejects_empty_outputs():
    with pytest.raises(ValueError):
        Transaction((), ())


def test_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        Transaction((), (TxOutput("a", 0),))
