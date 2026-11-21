import pytest

from pow51sim.core.pow import ProofOfWork


def test_zero_difficulty_accepts_any_hash():
    assert ProofOfWork(0).meets_target("f" * 64)


def test_target_depends_on_leading_zero_bits():
    pow_ = ProofOfWork(8)
    assert pow_.meets_target("00" + "f" * 62)
    assert not pow_.meets_target("01" + "f" * 62)


def test_mine_finds_valid_block():
    pow_ = ProofOfWork(8)
    block = pow_.mine(1, "p", "m", 1)
    assert pow_.meets_target(block.hash)
    assert block.has_valid_hash()


def test_mine_gives_up_after_max_attempts():
    with pytest.raises(RuntimeError):
        ProofOfWork(difficulty_bits=64, max_attempts=10).mine(1, "p", "m", 1)
