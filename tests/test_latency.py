from random import Random

import pytest

from pow51sim.simulation.latency import ExponentialLatency, FixedLatency


def test_fixed_latency_is_constant():
    assert FixedLatency(3.0).sample(Random(0)) == 3.0


def test_exponential_latency_mean_matches():
    rng = Random(1)
    samples = [ExponentialLatency(4.0).sample(rng) for _ in range(5000)]
    assert sum(samples) / len(samples) == pytest.approx(4.0, rel=0.1)


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        FixedLatency(-1)
    with pytest.raises(ValueError):
        ExponentialLatency(0)
