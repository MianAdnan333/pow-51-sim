from core.block import Block
from core.blockchain import Blockchain
from core.transaction import coinbase
from miners.honest import HonestMiner
from miners.network import Event, EventKind, Network


def honest_network(shares: list[float], seed: int = 0, **options: float) -> Network:
    miners = [HonestMiner(f"h{i}", share) for i, share in enumerate(shares)]
    return Network(miners, seed=seed, **options)  # type: ignore[arg-type]


def found_events(network: Network) -> list[Event]:
    return [e for e in network.log if e.kind is EventKind.BLOCK_FOUND]


def child(parent: Block, miner: str = "x") -> Block:
    height = parent.index + 1
    return Block(height, parent.hash, miner, (coinbase(miner, 50, height),), 0, height)


def all_blocks(chain: Blockchain) -> list[Block]:
    return [*chain.main_chain(), *chain.orphaned_blocks()]
