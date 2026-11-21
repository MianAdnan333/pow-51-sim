from dataclasses import replace

import pytest

from core.block import Block
from core.blockchain import AddResult, Blockchain
from core.consensus import BasicRule
from core.transaction import coinbase

from .helpers import child, extend

GENESIS = Block.genesis()


class RejectEverything:
    def validate(self, block: Block, chain: list[Block]) -> bool:
        return False


class RecordingRule:
    def __init__(self) -> None:
        self.seen: list[list[Block]] = []

    def validate(self, block: Block, chain: list[Block]) -> bool:
        self.seen.append(chain)
        return True


class ReorgRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[list[Block], list[Block]]] = []

    def __call__(self, old_chain: list[Block], new_chain: list[Block]) -> None:
        self.events.append((old_chain, new_chain))


def test_genesis_is_the_initial_tip():
    chain = Blockchain()
    assert chain.tip == GENESIS
    assert chain.main_chain() == [GENESIS]
    assert chain.forks() == [GENESIS]
    assert chain.orphaned_blocks() == []


def test_linear_chain_of_five_is_accepted():
    chain = Blockchain()
    parent = chain.tip
    for _ in range(5):
        block = child(parent)
        assert chain.add_block(block) is AddResult.ACCEPTED
        parent = block
    assert len(chain.main_chain()) == 6
    assert chain.tip == parent


def test_wrong_index_is_rejected_and_not_stored():
    block = Block(5, GENESIS.hash, "m", (coinbase("m", 50, 5),), 0, 1)
    chain = Blockchain()
    assert chain.add_block(block) is AddResult.REJECTED
    assert block.hash not in chain


def test_block_without_coinbase_is_rejected():
    assert Blockchain().add_block(replace(child(GENESIS), txs=())) is AddResult.REJECTED


def test_unknown_parent_is_an_orphan_and_not_stored():
    stray = child(child(GENESIS))
    chain = Blockchain()
    assert chain.add_block(stray) is AddResult.ORPHAN
    assert stray.hash not in chain
    assert chain.tip == GENESIS


def test_duplicate_block_is_ignored():
    recorder = ReorgRecorder()
    chain = Blockchain(on_reorg=recorder)
    block = child(GENESIS)
    chain.add_block(block)
    assert chain.add_block(block) is AddResult.ACCEPTED
    assert recorder.events == []
    assert len(chain.main_chain()) == 2
    assert len(chain.forks()) == 1


def test_fork_keeps_the_first_seen_tip():
    chain = Blockchain()
    first, second = child(GENESIS, "a"), child(GENESIS, "b")
    chain.add_block(first)
    chain.add_block(second)
    assert chain.tip == first
    assert chain.forks() == [first, second]


def test_longer_branch_wins_and_fires_on_reorg_with_both_chains():
    recorder = ReorgRecorder()
    chain = Blockchain(on_reorg=recorder)
    a1, a2 = extend(chain, GENESIS, 2, "a")
    b1, b2, b3 = extend(chain, GENESIS, 3, "b")
    assert chain.tip == b3
    assert recorder.events == [([GENESIS, a1, a2], [GENESIS, b1, b2, b3])]


def test_orphaned_blocks_are_exactly_the_losing_branch():
    chain = Blockchain()
    a1, a2 = extend(chain, GENESIS, 2, "a")
    extend(chain, GENESIS, 3, "b")
    assert chain.orphaned_blocks() == [a1, a2]
    assert set(chain.forks()) == {a2, chain.tip}


def test_no_reorg_event_for_extensions_or_shorter_forks():
    recorder = ReorgRecorder()
    chain = Blockchain(on_reorg=recorder)
    extend(chain, GENESIS, 3, "a")
    extend(chain, GENESIS, 2, "b")
    extend(chain, chain.tip, 1, "a")
    assert recorder.events == []


def test_reorg_fires_every_time_the_tip_switches_branch():
    recorder = ReorgRecorder()
    chain = Blockchain(on_reorg=recorder)
    a_blocks = extend(chain, GENESIS, 2, "a")
    b_blocks = extend(chain, GENESIS, 3, "b")
    a_blocks += extend(chain, a_blocks[-1], 2, "a")
    assert len(recorder.events) == 2
    old_chain, new_chain = recorder.events[1]
    assert old_chain == [GENESIS, *b_blocks]
    assert new_chain == [GENESIS, *a_blocks]


def test_on_extend_fires_for_tip_extensions_but_not_reorgs_or_side_blocks():
    extended: list[Block] = []
    recorder = ReorgRecorder()
    chain = Blockchain(on_reorg=recorder, on_extend=extended.append)
    a1, a2 = extend(chain, GENESIS, 2, "a")
    extend(chain, GENESIS, 1, "b")
    assert extended == [a1, a2]
    extend(chain, GENESIS, 3, "c")
    assert extended == [a1, a2]
    assert len(recorder.events) == 1


def test_chain_to_returns_the_path_for_any_block():
    chain = Blockchain()
    a1, a2 = extend(chain, GENESIS, 2, "a")
    (b1,) = extend(chain, a1, 1, "b")
    assert chain.chain_to(b1.hash) == [GENESIS, a1, b1]
    assert chain.chain_to(a2.hash) == [GENESIS, a1, a2]
    with pytest.raises(KeyError):
        chain.chain_to("missing")


def test_injected_rule_that_rejects_everything():
    chain = Blockchain(rules=[RejectEverything()])
    block = child(GENESIS)
    assert chain.add_block(block) is AddResult.REJECTED
    assert chain.tip == GENESIS


def test_every_injected_rule_must_pass():
    chain = Blockchain(rules=[BasicRule(), RejectEverything()])
    assert chain.add_block(child(GENESIS)) is AddResult.REJECTED


def test_rules_see_the_chain_the_block_would_extend():
    spy = RecordingRule()
    chain = Blockchain(rules=[BasicRule(), spy])
    a1, a2 = extend(chain, GENESIS, 2, "a")
    extend(chain, GENESIS, 1, "b")
    assert spy.seen[0] == [GENESIS]
    assert spy.seen[1] == [GENESIS, a1]
    assert spy.seen[2] == [GENESIS]
    assert chain.tip == a2


def test_rules_can_be_omitted_entirely():
    chain = Blockchain(rules=[])
    assert chain.add_block(replace(child(GENESIS), txs=())) is AddResult.ACCEPTED
