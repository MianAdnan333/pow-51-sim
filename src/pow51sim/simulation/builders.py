from collections.abc import Sequence

from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import ConsensusRule
from pow51sim.miners.base import Miner
from pow51sim.miners.honest import HonestMiner
from pow51sim.miners.malicious import MaliciousMiner
from pow51sim.simulation.latency import ExponentialLatency, FixedLatency, LatencyModel
from pow51sim.simulation.network import Network


def build_network(
    malicious_share: float,
    honest_count: int,
    block_interval: float = 600.0,
    mean_latency: float = 2.0,
    confirmations: int = 6,
    seed: int = 0,
    rules: Sequence[ConsensusRule] | None = None,
) -> Network:
    """Honest miners split the hash power left over by the malicious miner equally."""
    if honest_count < 1:
        raise ValueError("honest_count must be at least 1")
    honest_share = (1.0 - malicious_share) / honest_count
    miners: list[Miner] = [
        HonestMiner(f"honest-{i}", honest_share, Blockchain(rules))
        for i in range(honest_count)
    ]
    if malicious_share > 0:
        public = Blockchain(rules)
        miners.insert(
            0,
            MaliciousMiner(
                "malicious", malicious_share, public, confirmations=confirmations
            ),
        )
    latency: LatencyModel = (
        ExponentialLatency(mean_latency) if mean_latency > 0 else FixedLatency(0.0)
    )
    return Network(miners, block_interval, latency, seed)
