import pytest

from pow51sim.simulation.config import AttackConfig


@pytest.mark.parametrize(
    "kwargs",
    [
        {"attacker_share": -0.1},
        {"attacker_share": 1.1},
        {"attacker_share": 0.3, "confirmations": -1},
        {"attacker_share": 0.3, "honest_miners": 0},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        AttackConfig(**kwargs)


def test_defaults_describe_a_single_honest_miner():
    config = AttackConfig(0.3)
    assert config.honest_miners == 1
    assert config.max_reorg_depth is None
