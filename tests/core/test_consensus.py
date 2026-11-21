from dataclasses import replace

from core.block import Block
from core.consensus import BasicRule
from core.transaction import OutPoint, Transaction, TxOutput

from .helpers import child

GENESIS = Block.genesis()
RULE = BasicRule()


def test_genesis_is_valid_with_an_empty_chain():
    assert RULE.validate(GENESIS, [])


def test_a_proper_child_is_valid():
    assert RULE.validate(child(GENESIS), [GENESIS])


def test_wrong_prev_hash_is_invalid():
    block = replace(child(GENESIS), prev_hash="f" * 64)
    assert not RULE.validate(block, [GENESIS])


def test_wrong_index_is_invalid():
    block = replace(child(GENESIS), index=5)
    assert not RULE.validate(block, [GENESIS])


def test_forged_hash_is_invalid():
    block = child(GENESIS)
    object.__setattr__(block, "hash", "0" * 64)
    assert not RULE.validate(block, [GENESIS])


def test_block_without_transactions_is_invalid():
    assert not RULE.validate(replace(child(GENESIS), txs=()), [GENESIS])


def test_first_transaction_must_be_a_coinbase():
    spend = Transaction((OutPoint("x", 0),), (TxOutput("m", 1),))
    assert not RULE.validate(replace(child(GENESIS), txs=(spend,)), [GENESIS])


def test_non_genesis_block_cannot_claim_an_empty_chain():
    assert not RULE.validate(child(GENESIS), [])
