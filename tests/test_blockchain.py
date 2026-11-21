from dataclasses import replace

import pytest

from pow51sim.core.block import GENESIS, Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import ConsensusRule, InvalidBlockError
from pow51sim.core.rules import default_rules


def _extend(chain: Blockchain, parent: Block, miner: str, count: int, t: int = 1):
    blocks = []
    for i in range(count):
        parent = parent.child(miner, t + i)
        chain.add_block(parent)
        blocks.append(parent)
    return blocks


class _RejectMiner(ConsensusRule):
    def __init__(self, banned: str) -> None:
        self.banned = banned

    def validate(self, block, chain):
        if block.miner_id == self.banned:
            raise InvalidBlockError("banned miner")


def test_starts_at_genesis():
    chain = Blockchain()
    assert chain.tip == GENESIS
    assert chain.height == 0
    assert len(chain) == 1


def test_add_block_extends_tip():
    chain = Blockchain()
    block = GENESIS.child("a", 1)
    result = chain.add_block(block)
    assert chain.tip == block
    assert result.became_tip
    assert result.reorg_depth == 0


def test_duplicate_block_is_ignored():
    chain = Blockchain()
    block = GENESIS.child("a", 1)
    chain.add_block(block)
    assert not chain.add_block(block).became_tip
    assert len(chain) == 2


def test_unknown_parent_rejected():
    orphan = Block.create(5, "missing", "a", 1)
    with pytest.raises(InvalidBlockError):
        Blockchain().add_block(orphan)


def test_equal_length_fork_keeps_first_seen_tip():
    chain = Blockchain()
    first = _extend(chain, GENESIS, "a", 1)[0]
    _extend(chain, GENESIS, "b", 1)
    assert chain.tip == first
    assert len(chain.fork_tips()) == 1


def test_longer_fork_triggers_reorg_with_depth():
    chain = Blockchain()
    _extend(chain, GENESIS, "a", 2)
    fork = _extend(chain, GENESIS, "b", 3)
    assert chain.tip == fork[-1]
    assert [b.miner_id for b in chain.main_chain()[1:]] == ["b"] * 3


def test_reorg_depth_reported_on_overtaking_block():
    chain = Blockchain()
    _extend(chain, GENESIS, "a", 2)
    branch = GENESIS.child("b", 1)
    chain.add_block(branch)
    second = branch.child("b", 2)
    chain.add_block(second)
    result = chain.add_block(second.child("b", 3))
    assert result.reorg_depth == 2


def test_fork_tips_exclude_main_tip():
    chain = Blockchain()
    _extend(chain, GENESIS, "a", 2)
    side = _extend(chain, GENESIS, "b", 1)[0]
    assert chain.fork_tips() == [side]
    assert len(chain.tips()) == 2


def test_common_ancestor():
    chain = Blockchain()
    main = _extend(chain, GENESIS, "a", 2)
    side = _extend(chain, main[0], "b", 1)[0]
    assert chain.common_ancestor(main[1], side) == main[0]


def test_custom_rule_can_reject_blocks():
    chain = Blockchain([*default_rules(), _RejectMiner("evil")])
    with pytest.raises(InvalidBlockError):
        chain.add_block(GENESIS.child("evil", 1))
    assert chain.height == 0


def test_rejected_block_is_not_stored():
    chain = Blockchain([_RejectMiner("evil")])
    bad = GENESIS.child("evil", 1)
    with pytest.raises(InvalidBlockError):
        chain.add_block(bad)
    assert bad.hash not in chain


def test_validate_passes_for_well_formed_chain():
    chain = Blockchain()
    _extend(chain, GENESIS, "a", 3)
    assert chain.validate()


def test_validate_detects_tampering_under_stricter_rules():
    chain = Blockchain(rules=[])
    chain.add_block(replace(GENESIS.child("a", 1), miner_id="thief"))
    assert chain.validate()
    assert not chain.validate(default_rules())


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[list[Block], list[Block]]] = []

    def on_reorg(self, disconnected, connected):
        self.events.append((disconnected, connected))


def test_listener_gets_disconnected_and_connected_blocks_on_reorg():
    chain, recorder = Blockchain(), _Recorder()
    chain.subscribe(recorder)
    main = _extend(chain, GENESIS, "a", 2)
    fork = _extend(chain, GENESIS, "b", 3)
    disconnected, connected = recorder.events[-1]
    assert disconnected == [main[1], main[0]]
    assert connected == fork


def test_listener_not_called_for_side_forks():
    chain, recorder = Blockchain(), _Recorder()
    _extend(chain, GENESIS, "a", 2)
    chain.subscribe(recorder)
    _extend(chain, GENESIS, "b", 1)
    assert recorder.events == []


def test_listener_veto_leaves_chain_unchanged():
    class Veto:
        def on_reorg(self, disconnected, connected):
            raise InvalidBlockError("veto")

    chain = Blockchain()
    chain.subscribe(Veto())
    block = GENESIS.child("a", 1)
    with pytest.raises(InvalidBlockError):
        chain.add_block(block)
    assert chain.height == 0
    assert block.hash not in chain


def test_branch_runs_from_genesis_to_given_block():
    chain = Blockchain()
    blocks = _extend(chain, GENESIS, "a", 2)
    assert chain.branch(blocks[0]) == [GENESIS, blocks[0]]


def test_copy_is_independent():
    chain = Blockchain()
    clone = chain.copy()
    _extend(clone, GENESIS, "a", 2)
    assert chain.height == 0
    assert clone.height == 2
