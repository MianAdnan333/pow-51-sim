from pow51sim.core.block import GENESIS
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.rules import UtxoRule, default_rules
from pow51sim.core.transaction import Transaction, TxOutput
from pow51sim.defense.comparator import ChainComparator

from .helpers import extend, funding_block, spend

compare = ChainComparator().compare


def test_double_spend_flags_competing_chain_as_fraudulent():
    funding, [coin, _] = funding_block(50, 30)
    payment = spend(coin, "victim")
    refund = spend(coin, "alice", nonce=1)
    honest = [GENESIS, funding, *extend(funding, "honest", (payment,), ())]
    competing = [GENESIS, funding, *extend(funding, "attacker", (refund,), (), ())]

    report = compare(honest, competing)

    assert report.fraudulent
    assert report.fork_index == 1
    [conflict] = report.conflicts
    assert conflict.outpoint == coin
    assert conflict.honest_tx == payment
    assert conflict.competing_tx == refund


def test_clean_fork_is_not_flagged():
    funding, [coin_a, coin_b] = funding_block(50, 30)
    honest = [GENESIS, funding, *extend(funding, "h", (spend(coin_a, "bob"),))]
    competing = [GENESIS, funding, *extend(funding, "c", (spend(coin_b, "carol", 30),))]

    report = compare(honest, competing)

    assert not report.fraudulent
    assert report.conflicts == ()
    assert report.fork_index == 1


def test_same_transaction_in_both_branches_is_not_a_conflict():
    funding, [coin, _] = funding_block(50, 30)
    payment = spend(coin, "bob")
    honest = [GENESIS, funding, *extend(funding, "h", (payment,))]
    competing = [GENESIS, funding, *extend(funding, "c", (payment,), ())]
    assert not compare(honest, competing).fraudulent


def test_same_spend_with_identical_outputs_is_not_a_conflict():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *extend(funding, "h", (spend(coin, "bob"),))]
    competing = [
        GENESIS,
        funding,
        *extend(funding, "c", (spend(coin, "bob", nonce=9),)),
    ]
    assert not compare(honest, competing).fraudulent


def test_same_input_with_different_amount_is_a_conflict():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *extend(funding, "h", (spend(coin, "bob", 50),))]
    competing = [GENESIS, funding, *extend(funding, "c", (spend(coin, "bob", 40),))]
    assert compare(honest, competing).fraudulent


def test_conflict_is_found_across_different_heights():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *extend(funding, "h", (), (), (spend(coin, "bob"),))]
    competing = [
        GENESIS,
        funding,
        *extend(funding, "c", (spend(coin, "eve", nonce=1),)),
    ]
    assert compare(honest, competing).fraudulent


def test_each_conflicting_outpoint_is_reported():
    funding, [coin_a, coin_b] = funding_block(50, 30)
    honest = [
        GENESIS,
        funding,
        *extend(funding, "h", (spend(coin_a, "bob"), spend(coin_b, "bob", 30))),
    ]
    sweep = Transaction((coin_a, coin_b), (TxOutput("eve", 80),))
    competing = [GENESIS, funding, *extend(funding, "c", (sweep,))]
    assert len(compare(honest, competing).conflicts) == 2


def test_competing_chain_extending_honest_chain_is_clean():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *extend(funding, "h", (spend(coin, "bob"),))]
    competing = [*honest, *extend(honest[-1], "c", ())]
    report = compare(honest, competing)
    assert not report.fraudulent
    assert report.fork_index == honest[-1].index


def test_identical_chains_are_clean():
    funding, _ = funding_block(50)
    chain = [GENESIS, funding]
    report = compare(chain, chain)
    assert not report.fraudulent
    assert report.fork_index == 1


def test_works_on_real_chains_with_utxo_validation():
    rules = [*default_rules(), UtxoRule()]
    honest, private = Blockchain(rules), Blockchain(rules)
    funding, [coin, _] = funding_block(50, 30)
    honest.add_block(funding)
    private.add_block(funding)
    for block in extend(funding, "honest", (spend(coin, "victim"),), ()):
        honest.add_block(block)
    for block in extend(funding, "attacker", (spend(coin, "alice", nonce=1),)):
        private.add_block(block)

    report = compare(honest.main_chain(), private.main_chain())

    assert report.fraudulent
    assert report.fork_index == funding.index
