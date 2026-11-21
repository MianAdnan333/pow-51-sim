from core.block import Block
from core.transaction import Transaction, TxOutput
from defense.comparator import ChainComparator

from .helpers import GENESIS, block_on, funding_block, spend

compare = ChainComparator().compare


def _branch(
    parent: Block, miner: str, *tx_groups: tuple[Transaction, ...]
) -> list[Block]:
    blocks = []
    for txs in tx_groups or ((),):
        parent = block_on(parent, miner, txs)
        blocks.append(parent)
    return blocks


def test_double_spend_is_fraudulent():
    funding, [coin, _] = funding_block(50, 30)
    payment, refund = spend(coin, "victim"), spend(coin, "attacker")
    honest = [GENESIS, funding, *_branch(funding, "h", (payment,), ())]
    competing = [GENESIS, funding, *_branch(funding, "a", (refund,), (), ())]

    result = compare(honest, competing)

    assert result.is_fraudulent
    assert result.conflicting_outpoints == (coin,)
    assert result.fork_height == 1


def test_clean_fork_is_not_fraudulent():
    funding, [coin_a, coin_b] = funding_block(50, 30)
    honest = [GENESIS, funding, *_branch(funding, "h", (spend(coin_a, "bob"),))]
    competing = [
        GENESIS,
        funding,
        *_branch(funding, "c", (spend(coin_b, "carol", 30),)),
    ]

    result = compare(honest, competing)

    assert not result.is_fraudulent
    assert result.conflicting_outpoints == ()
    assert result.fork_height == 1


def test_the_same_transaction_on_both_branches_is_not_a_conflict():
    funding, [coin, _] = funding_block(50, 30)
    payment = spend(coin, "bob")
    honest = [GENESIS, funding, *_branch(funding, "h", (payment,))]
    competing = [GENESIS, funding, *_branch(funding, "c", (payment,), ())]
    assert not compare(honest, competing).is_fraudulent


def test_a_different_transaction_spending_the_same_output_is_a_conflict():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *_branch(funding, "h", (spend(coin, "bob", 50),))]
    competing = [GENESIS, funding, *_branch(funding, "c", (spend(coin, "bob", 40),))]
    assert compare(honest, competing).is_fraudulent


def test_each_conflicting_outpoint_is_reported_once():
    funding, [coin_a, coin_b] = funding_block(50, 30)
    honest = [
        GENESIS,
        funding,
        *_branch(funding, "h", (spend(coin_a, "bob"), spend(coin_b, "bob", 30))),
    ]
    sweep = Transaction((coin_a, coin_b), (TxOutput("eve", 80),))
    competing = [GENESIS, funding, *_branch(funding, "c", (sweep,))]
    assert set(compare(honest, competing).conflicting_outpoints) == {coin_a, coin_b}


def test_conflicts_are_found_at_different_heights():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *_branch(funding, "h", (), (), (spend(coin, "bob"),))]
    competing = [GENESIS, funding, *_branch(funding, "c", (spend(coin, "eve"),))]
    assert compare(honest, competing).is_fraudulent


def test_a_chain_extending_the_honest_one_is_clean():
    funding, [coin, _] = funding_block(50, 30)
    honest = [GENESIS, funding, *_branch(funding, "h", (spend(coin, "bob"),))]
    competing = [*honest, *_branch(honest[-1], "c")]
    result = compare(honest, competing)
    assert not result.is_fraudulent
    assert result.fork_height == honest[-1].index


def test_identical_chains_are_clean():
    funding, _ = funding_block(50)
    chain = [GENESIS, funding]
    result = compare(chain, chain)
    assert not result.is_fraudulent
    assert result.fork_height == 1
