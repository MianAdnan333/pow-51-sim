from dataclasses import FrozenInstanceError, replace

import pytest

from core.block import GENESIS_PREV_HASH, Block
from core.transaction import coinbase

BASE = Block(1, "p" * 64, "miner", (coinbase("miner", 50, 1),), 0, 10)


def test_hash_is_deterministic():
    twin = Block(1, "p" * 64, "miner", (coinbase("miner", 50, 1),), 0, 10)
    assert twin.hash == BASE.hash
    assert BASE.has_valid_hash()


@pytest.mark.parametrize(
    "variant",
    [
        replace(BASE, index=2),
        replace(BASE, prev_hash="q" * 64),
        replace(BASE, miner_id="other"),
        replace(BASE, txs=(coinbase("miner", 51, 1),)),
        replace(BASE, txs=()),
        replace(BASE, nonce=1),
        replace(BASE, timestamp=11),
    ],
)
def test_changing_any_field_changes_the_hash(variant):
    assert variant.hash != BASE.hash
    assert variant.has_valid_hash()


def test_genesis_is_fixed():
    genesis = Block.genesis()
    assert genesis == Block.genesis()
    assert genesis.hash == Block.genesis().hash
    assert genesis.index == 0
    assert genesis.prev_hash == GENESIS_PREV_HASH == "0" * 64
    assert genesis.has_valid_hash()


def test_tampering_after_construction_is_detectable():
    forged = replace(BASE)
    object.__setattr__(forged, "miner_id", "thief")
    assert not forged.has_valid_hash()


def test_blocks_are_immutable():
    with pytest.raises(FrozenInstanceError):
        BASE.nonce = 5  # type: ignore[misc]
