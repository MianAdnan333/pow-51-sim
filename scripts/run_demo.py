"""Quick demo: double-spend success rate with and without the defense."""

from random import Random

from pow51sim.defense.rules import build_rules
from pow51sim.simulation.config import AttackConfig
from pow51sim.simulation.scenario import AttackScenario

SHARES = (0.2, 0.3, 0.4, 0.5, 0.6)
CONFIRMATIONS = 3
TRIALS = 200
THRESHOLD = 6


def success_rate(share: float, defense: bool) -> float:
    config = AttackConfig(share, CONFIRMATIONS, honest_miners=10)
    rules = build_rules(None, max_consecutive=THRESHOLD if defense else None)
    wins = sum(
        AttackScenario(config, rules, Random(seed)).run().success
        for seed in range(TRIALS)
    )
    return wins / TRIALS


def main() -> None:
    print(f"Double-spend success ({TRIALS} trials, {CONFIRMATIONS} confirmations)")
    print("attacker share | no defense | defense on")
    for share in SHARES:
        off, on = success_rate(share, False), success_rate(share, True)
        print(f"{share:>14.0%} | {off:>10.0%} | {on:>10.0%}")


if __name__ == "__main__":
    main()
