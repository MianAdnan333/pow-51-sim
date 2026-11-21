"""Fast NumPy model of the attack race, used for single-race replays and exact curves.

It mirrors the rules of the full simulator (release when longer and confirmed, the
LPC rule accepting at most `lpc_limit - 1` private blocks) without its network, so one
replay costs microseconds. The grid results shown in the dashboard come from the real
simulator (`dashboard.engine.run_grid`).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from numpy.typing import NDArray

MAX_ROUNDS = 500
GIVE_UP_DEFICIT = 10
FALSE_POSITIVE_WINDOW = 144
SHARE_SCALE = 10_000

BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int64]


@dataclass(frozen=True)
class SimParams:
    trials: int = 500
    confirmations: int = 3
    lpc_limit: int = 6
    seed: int = 0
    max_rounds: int = MAX_ROUNDS
    give_up_deficit: int = GIVE_UP_DEFICIT

    def __post_init__(self) -> None:
        if self.trials < 1 or self.max_rounds < 1:
            raise ValueError("trials and max_rounds must be at least 1")
        if self.confirmations < 0:
            raise ValueError("confirmations must be non-negative")
        if self.lpc_limit < 2:
            raise ValueError("lpc_limit must be at least 2")


@dataclass(frozen=True)
class RaceTrace:
    events: tuple[str, ...]
    honest_blocks: int
    private_blocks: int
    accepted_private_blocks: int
    released: bool
    accepted: bool
    blocked_by_safe_mode: bool
    reorg_depth: int
    defense: bool
    reason: str


@dataclass(frozen=True)
class _Outcome:
    success: BoolArray
    blocked: BoolArray
    private_len: IntArray
    honest_len: IntArray
    reorg_depth: IntArray
    stop_round: IntArray


def race_trace(share: float, params: SimParams, defense: bool, seed: int) -> RaceTrace:
    """Replay one attack; a seed gives the same race with or without defense."""
    _validate_shares([share])
    single = replace(params, seed=seed, trials=1)
    wins = _draw(share, single)
    outcome = _race(wins, single, defense)
    stop = int(outcome.stop_round[0])
    events = tuple("A" if won else "H" for won in wins[:stop, 0])
    return _describe(events, outcome, single, defense, stop)


def honest_limit_probability(
    shares: Sequence[float], limit: int, blocks: int = FALSE_POSITIVE_WINDOW
) -> pd.DataFrame:
    """Exact chance a miner mines `limit` blocks in a row within `blocks` blocks."""
    if limit < 2 or blocks < 1:
        raise ValueError("limit must be at least 2 and blocks at least 1")
    _validate_shares(shares)
    win = np.asarray(shares, dtype=float)[:, None]
    state = np.zeros((len(shares), limit))
    state[:, 0] = 1.0
    hit = np.zeros(len(shares))
    for _ in range(blocks):
        advance = state * win
        hit += advance[:, -1]
        following = np.zeros_like(state)
        following[:, 1:] = advance[:, :-1]
        following[:, 0] = (state * (1.0 - win)).sum(axis=1)
        state = following
    curve: pd.DataFrame = pd.DataFrame({"hash_share": list(shares), "probability": hit})
    return curve


def _validate_shares(shares: Sequence[float]) -> None:
    if len(shares) == 0:
        raise ValueError("shares must not be empty")
    if any(not 0.0 <= share <= 1.0 for share in shares):
        raise ValueError("shares must be within [0, 1]")


def _draw(share: float, params: SimParams) -> BoolArray:
    stream = np.random.default_rng([params.seed, round(share * SHARE_SCALE)])
    draws: BoolArray = stream.random((params.max_rounds, params.trials)) < share
    return draws


def _race(wins: BoolArray, params: SimParams, defense: bool) -> _Outcome:
    rounds, trials = wins.shape
    attacker = np.zeros(trials, dtype=np.int64)
    honest = np.zeros(trials, dtype=np.int64)
    active = np.ones(trials, dtype=bool)
    success = np.zeros(trials, dtype=bool)
    blocked = np.zeros(trials, dtype=bool)
    depth = np.zeros(trials, dtype=np.int64)
    stop = np.full(trials, rounds, dtype=np.int64)
    for round_no in range(rounds):
        if not active.any():
            break
        attacker += active & wins[round_no]
        honest += active & ~wins[round_no]
        confirmed = honest >= params.confirmations
        lead = attacker - honest
        release = active & confirmed & (lead > 0)
        gave_up = active & confirmed & (-lead > params.give_up_deficit)
        accepted, rejected = _judge(release, attacker, honest, params, defense)
        success |= accepted
        blocked |= rejected
        depth = np.where(accepted, honest, depth)
        finished = release | gave_up
        stop = np.where(finished, round_no + 1, stop)
        active &= ~finished
    return _Outcome(success, blocked, attacker, honest, depth, stop)


def _judge(
    release: BoolArray,
    attacker: IntArray,
    honest: IntArray,
    params: SimParams,
    defense: bool,
) -> tuple[BoolArray, BoolArray]:
    """Defense accepts at most `lpc_limit - 1` private blocks, so it wins only if
    that prefix already overtakes the honest chain."""
    if not defense:
        return release, np.zeros_like(release)
    over_limit = release & (attacker >= params.lpc_limit)
    prefix_overtakes = over_limit & (params.lpc_limit - 1 > honest)
    accepted = (release & ~over_limit) | prefix_overtakes
    return accepted, over_limit & ~prefix_overtakes


def _describe(
    events: tuple[str, ...],
    outcome: _Outcome,
    params: SimParams,
    defense: bool,
    stop: int,
) -> RaceTrace:
    private = int(outcome.private_len[0])
    honest = int(outcome.honest_len[0])
    accepted = bool(outcome.success[0])
    blocked = bool(outcome.blocked[0])
    released = accepted or blocked
    over_limit = defense and private >= params.lpc_limit
    kept = params.lpc_limit - 1 if over_limit and released else private
    if accepted:
        reason = f"Private chain replaced {honest} honest blocks"
        if over_limit:
            reason += f"; only its first {kept} blocks were accepted"
    elif blocked:
        reason = (
            f"{private} consecutive private blocks hit the LPC limit "
            f"({params.lpc_limit}); Safe Mode refused the reorg"
        )
    elif stop < params.max_rounds:
        reason = "The honest chain outran the attacker, who gave up"
    else:
        reason = "The attacker never overtook the honest chain"
    return RaceTrace(
        events=events,
        honest_blocks=honest,
        private_blocks=private,
        accepted_private_blocks=kept,
        released=released,
        accepted=accepted,
        blocked_by_safe_mode=blocked,
        reorg_depth=int(outcome.reorg_depth[0]),
        defense=defense,
        reason=reason,
    )
