import pytest

from core.block import Block
from core.blockchain import AddResult, Blockchain
from core.pow import Difficulty, mine

from .helpers import child

TEMPLATE = child(Block.genesis())


def test_default_difficulty_is_low():
    assert Difficulty.DEFAULT_BITS in (2, 3)


def test_meets_target_counts_leading_hex_zeros():
    assert Difficulty.meets_target("00ab" + "f" * 60, bits=2)
    assert not Difficulty.meets_target("0aab" + "f" * 60, bits=2)
    assert Difficulty.meets_target("f" * 64, bits=0)
    assert not Difficulty.meets_target("00ab" + "f" * 60, bits=3)


def test_mine_produces_a_block_meeting_the_default_target():
    mined = mine(TEMPLATE)
    assert Difficulty.meets_target(mined.hash)
    assert mined.has_valid_hash()


def test_mine_keeps_everything_but_the_nonce():
    mined = mine(TEMPLATE)
    assert mined.nonce >= TEMPLATE.nonce
    assert (mined.index, mined.prev_hash, mined.miner_id, mined.txs) == (
        TEMPLATE.index,
        TEMPLATE.prev_hash,
        TEMPLATE.miner_id,
        TEMPLATE.txs,
    )
    assert TEMPLATE.nonce == 0


def test_harder_target_needs_more_zeros():
    mined = mine(TEMPLATE, bits=3)
    assert mined.hash.startswith("000")


def test_mine_is_deterministic():
    assert mine(TEMPLATE) == mine(TEMPLATE)


def test_mined_block_is_accepted_by_the_chain():
    chain = Blockchain()
    assert chain.add_block(mine(TEMPLATE)) is AddResult.ACCEPTED


def test_mine_gives_up_after_max_attempts():
    with pytest.raises(RuntimeError):
        mine(TEMPLATE, bits=64, max_attempts=5)
