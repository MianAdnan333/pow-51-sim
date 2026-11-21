import pytest

from core.blockchain import Blockchain
from core.transaction import OutPoint, Transaction, TxOutput, coinbase
from defense.utxo import UTXOSet

from .helpers import GENESIS, block_on, funding_block, spend


def test_apply_block_adds_outputs():
    utxos = UTXOSet()
    block = block_on(GENESIS, "miner")
    utxos.apply_block(block)
    reward = OutPoint(block.txs[0].tx_id, 0)
    assert utxos.is_unspent(reward)
    assert utxos.get(reward) == TxOutput("miner", 50)
    assert utxos.balance("miner") == 50
    assert len(utxos) == 1


def test_spend_consumes_the_input_and_creates_the_output():
    funding, [coin] = funding_block(50)
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(block_on(funding, "m", (spend(coin, "bob"),)))
    assert not utxos.is_unspent(coin)
    assert utxos.balance("alice") == 0
    assert utxos.balance("bob") == 50


def test_rollback_restores_spent_outputs_and_removes_created_ones():
    funding, [coin] = funding_block(50)
    spending = block_on(funding, "m", (spend(coin, "bob"),))
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(spending)
    utxos.rollback_block(spending)
    assert utxos.is_unspent(coin)
    assert utxos.balance("bob") == 0
    assert utxos.balance("m") == 0


def test_rollback_handles_an_output_created_and_spent_in_the_same_block():
    funding, [coin] = funding_block(50)
    first = spend(coin, "bob")
    second = spend(OutPoint(first.tx_id, 0), "carol")
    block = block_on(funding, "m", (first, second))
    utxos = UTXOSet()
    utxos.apply_block(funding)
    utxos.apply_block(block)
    assert utxos.balance("carol") == 50
    utxos.rollback_block(block)
    assert utxos.is_unspent(coin)
    assert utxos.balance("carol") == 0
    assert utxos.balance("bob") == 0


def test_rollback_of_an_unapplied_block_is_an_error():
    with pytest.raises(ValueError):
        UTXOSet().rollback_block(block_on(GENESIS))


def test_spending_an_unknown_output_is_ignored():
    ghost = Transaction((OutPoint("nope", 0),), (TxOutput("eve", 1),))
    utxos = UTXOSet()
    utxos.apply_block(block_on(GENESIS, "m", (ghost,)))
    assert utxos.balance("eve") == 1


def test_rebuild_matches_incremental_updates():
    funding, [coin] = funding_block(50)
    spending = block_on(funding, "m", (spend(coin, "bob"),))
    incremental = UTXOSet()
    for block in (GENESIS, funding, spending):
        incremental.apply_block(block)
    rebuilt = UTXOSet()
    rebuilt.apply_block(block_on(GENESIS, "stale"))
    rebuilt.rebuild([GENESIS, funding, spending])
    assert len(rebuilt) == len(incremental)
    assert rebuilt.balance("bob") == incremental.balance("bob") == 50
    assert rebuilt.balance("stale") == 0


def _tracked_chain() -> tuple[Blockchain, UTXOSet]:
    utxos = UTXOSet()
    chain = Blockchain(on_reorg=utxos.on_reorg, on_extend=utxos.apply_block)
    return chain, utxos


def test_follows_the_main_chain_as_blocks_extend_it():
    chain, utxos = _tracked_chain()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    assert utxos.balance("alice") == 50
    chain.add_block(block_on(funding, "m", (spend(coin, "bob"),)))
    assert utxos.balance("bob") == 50
    assert utxos.balance("alice") == 0


def test_rolls_back_the_old_branch_and_applies_the_new_one_on_reorg():
    chain, utxos = _tracked_chain()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    payment = spend(coin, "victim")
    refund = spend(coin, "attacker")
    honest_1 = block_on(funding, "h1", (payment,))
    honest_2 = block_on(honest_1, "h2")
    for block in (honest_1, honest_2):
        chain.add_block(block)
    assert utxos.balance("victim") == 50

    private = block_on(funding, "a", (refund,))
    private_blocks = [
        private,
        block_on(private, "a"),
        block_on(block_on(private, "a"), "a"),
    ]
    private_blocks[2] = block_on(private_blocks[1], "a")
    for block in private_blocks:
        chain.add_block(block)

    assert chain.tip == private_blocks[2]
    assert utxos.balance("victim") == 0
    assert utxos.balance("attacker") == 50
    assert utxos.balance("h1") == 0
    assert not utxos.is_unspent(OutPoint(payment.tx_id, 0))


def test_side_blocks_do_not_touch_the_utxo_set():
    chain, utxos = _tracked_chain()
    funding, [coin] = funding_block(50)
    chain.add_block(funding)
    first = block_on(funding, "h1", (spend(coin, "bob"),))
    chain.add_block(first)
    chain.add_block(block_on(funding, "x", (spend(coin, "carol"),)))
    assert utxos.balance("bob") == 50
    assert utxos.balance("carol") == 0
    assert coinbase("h1", 50, 2).tx_id == first.txs[0].tx_id
