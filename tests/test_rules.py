from dataclasses import replace

import pytest

from pow51sim.core.block import GENESIS, Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import InvalidBlockError
from pow51sim.core.pow import ProofOfWork
from pow51sim.core.rules import (
    IntegrityRule,
    LinkageRule,
    ProofOfWorkRule,
    TimestampRule,
    UtxoRule,
    default_rules,
)
from pow51sim.core.transaction import OutPoint, Transaction, TxOutput


def _coinbase(nonce: int = 0, amount: int = 50) -> Transaction:
    return Transaction((), (TxOutput("alice", amount),), nonce)


def _spend(source: Transaction, to: str = "bob", amount: int = 50) -> Transaction:
    return Transaction((OutPoint(source.tx_id, 0),), (TxOutput(to, amount),))


def _utxo_chain() -> tuple[Blockchain, Block, Transaction]:
    chain = Blockchain([*default_rules(), UtxoRule()])
    funding = _coinbase()
    block = GENESIS.child("m", 1, txs=(funding,))
    chain.add_block(block)
    return chain, block, funding


def test_integrity_rule_rejects_tampered_block():
    block = replace(GENESIS.child("m", 1), miner_id="thief")
    with pytest.raises(InvalidBlockError):
        IntegrityRule().validate(block, Blockchain())


def test_linkage_rule_rejects_wrong_index():
    block = Block.create(7, GENESIS.hash, "m", 1)
    with pytest.raises(InvalidBlockError):
        LinkageRule().validate(block, Blockchain())


def test_timestamp_rule_rejects_time_travel():
    chain = Blockchain()
    parent = GENESIS.child("m", 10)
    chain.add_block(parent)
    with pytest.raises(InvalidBlockError):
        TimestampRule().validate(parent.child("m", 5), chain)


def test_pow_rule_enforces_target():
    rule = ProofOfWorkRule(ProofOfWork(difficulty_bits=16))
    chain = Blockchain()
    unlucky = next(
        b
        for n in range(100)
        if not (b := Block.create(1, GENESIS.hash, "m", 1, nonce=n)).hash.startswith(
            "0000"
        )
    )
    with pytest.raises(InvalidBlockError):
        rule.validate(unlucky, chain)


def test_pow_rule_accepts_mined_block():
    pow_ = ProofOfWork(8)
    block = pow_.mine(1, GENESIS.hash, "m", 1)
    ProofOfWorkRule(pow_).validate(block, Blockchain())


def test_utxo_accepts_valid_spend():
    chain, parent, funding = _utxo_chain()
    chain.add_block(parent.child("m", 2, txs=(_spend(funding),)))
    assert chain.height == 2


def test_utxo_rejects_double_spend_on_same_branch():
    chain, parent, funding = _utxo_chain()
    spent = parent.child("m", 2, txs=(_spend(funding, "bob"),))
    chain.add_block(spent)
    with pytest.raises(InvalidBlockError):
        chain.add_block(spent.child("m", 3, txs=(_spend(funding, "carol"),)))


def test_utxo_rejects_double_spend_within_block():
    chain, parent, funding = _utxo_chain()
    block = parent.child("m", 2, txs=(_spend(funding, "bob"), _spend(funding, "eve")))
    with pytest.raises(InvalidBlockError):
        chain.add_block(block)


def test_utxo_allows_conflicting_spend_on_competing_fork():
    chain, parent, funding = _utxo_chain()
    chain.add_block(parent.child("m", 2, txs=(_spend(funding, "bob"),)))
    chain.add_block(parent.child("n", 2, txs=(_spend(funding, "carol"),)))
    assert len(chain.fork_tips()) == 1


def test_utxo_rejects_unknown_input():
    chain, parent, _ = _utxo_chain()
    ghost = Transaction((OutPoint("nope", 0),), (TxOutput("bob", 1),))
    with pytest.raises(InvalidBlockError):
        chain.add_block(parent.child("m", 2, txs=(ghost,)))


def test_utxo_rejects_outputs_exceeding_inputs():
    chain, parent, funding = _utxo_chain()
    with pytest.raises(InvalidBlockError):
        chain.add_block(parent.child("m", 2, txs=(_spend(funding, amount=51),)))


def test_utxo_rejects_second_coinbase():
    chain = Blockchain([*default_rules(), UtxoRule()])
    block = GENESIS.child("m", 1, txs=(_coinbase(0), _coinbase(1)))
    with pytest.raises(InvalidBlockError):
        chain.add_block(block)
