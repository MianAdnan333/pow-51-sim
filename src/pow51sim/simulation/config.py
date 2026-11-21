from dataclasses import dataclass


@dataclass(frozen=True)
class AttackConfig:
    attacker_share: float
    confirmations: int = 6
    max_rounds: int = 500
    give_up_deficit: int = 10
    max_reorg_depth: int | None = None
    honest_miners: int = 1

    def __post_init__(self) -> None:
        if not 0.0 <= self.attacker_share <= 1.0:
            raise ValueError("attacker_share must be within [0, 1]")
        if self.confirmations < 0:
            raise ValueError("confirmations must be non-negative")
        if self.honest_miners < 1:
            raise ValueError("honest_miners must be at least 1")
