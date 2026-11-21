from collections.abc import Sequence
from itertools import product
from random import Random

import pandas as pd

from pow51sim.defense.rules import build_rules
from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.scenario import AttackResult, AttackScenario


def run_trials(config: AttackConfig, trials: int, seed: int = 0) -> list[AttackResult]:
    rng = Random(seed)
    rules = build_rules(config.max_reorg_depth)
    return [AttackScenario(config, rules, rng).run() for _ in range(trials)]


def sweep(
    shares: Sequence[float],
    confirmations: Sequence[int],
    trials: int,
    seed: int = 0,
    reorg_limits: Sequence[int | None] = (None,),
) -> pd.DataFrame:
    rows = []
    for share, conf, limit in product(shares, confirmations, reorg_limits):
        config = AttackConfig(share, conf, max_reorg_depth=limit)
        results = run_trials(config, trials, seed)
        rows.append(
            {
                "attacker_share": share,
                "confirmations": conf,
                "reorg_limit": limit,
                "success_rate": sum(r.success for r in results) / trials,
                "mean_rounds": sum(r.rounds for r in results) / trials,
            }
        )
    frame: pd.DataFrame = pd.DataFrame(rows).astype({"reorg_limit": "Int64"})
    return frame
