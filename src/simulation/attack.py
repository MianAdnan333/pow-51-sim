from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from core.block import Block
from core.blockchain import Blockchain
from core.transaction import OutPoint, Transaction, TxOutput, coinbase
from defense.lpc import SafeModeStats, build_chain
from miners.honest import HonestMiner
from miners.malicious import MaliciousMiner
from miners.miner import Miner, to_broadcasts
from miners.network import Network

ATTACKER_ID = "attacker"
VICTIM_ID = "honest-0"
FAUCET_ID = "faucet"
COIN_VALUE = 50
DEFAULT_GIVE_UP_DEFICIT = 10
DEFAULT_BLOCKS_PER_RUN = 300


@dataclass(frozen=True)
class AttackResult:
    attack_success: bool
    private_len: int
    final_chain_length: int
    reorg_depth: int
    max_consecutive_by_one_miner: int
    blocked_by_safe_mode: bool
    orphan_rate: float
    miner_block_counts: dict[str, int]
    released: bool


class AttackScenario:
    """One double-spend attempt on a Network. Build it with `make_scenario`; run once.

    The attacker owns one coin and forks right before the victim is paid. Its private
    chain spends the same coin back to itself. Once the payment has
    `confirmation_depth` confirmations and the private chain is longer, the private
    chain is released. Success means the victim's chain ends up with the attacker's
    spend and without the payment. The attacker gives up when the honest chain
    leads by more than `give_up_deficit` blocks.
    """

    def __init__(
        self,
        network: Network,
        attacker_id: str,
        victim_id: str,
        confirmation_depth: int,
        defense_enabled: bool,
        max_time: float,
        give_up_deficit: int = DEFAULT_GIVE_UP_DEFICIT,
        safe_mode_stats: Sequence[SafeModeStats] = (),
    ) -> None:
        miners = {miner.miner_id: miner for miner in network.miners}
        attacker = miners[attacker_id]
        if not isinstance(attacker, MaliciousMiner):
            raise TypeError("attacker_id must name a MaliciousMiner")
        self.network = network
        self.attacker = attacker
        self.victim = miners[victim_id]
        self.honest = [m for m in network.miners if m is not attacker]
        self.confirmation_depth = confirmation_depth
        self.defense_enabled = defense_enabled
        self.max_time = max_time
        self.give_up_deficit = give_up_deficit
        self.safe_mode_stats = list(safe_mode_stats)
        self._fork_height = 0
        self._payment: Transaction
        self._refund: Transaction

    def run(self) -> AttackResult:
        self._prepare()
        while self.network.now < self.max_time:
            if self.network.step() is None:
                break
            if self._should_release():
                return self._release()
            if self._should_give_up():
                break
        return self._result(released=False, reorg_depth=0)

    def _prepare(self) -> None:
        genesis = self.attacker.chain.tip
        reward = coinbase(ATTACKER_ID, COIN_VALUE, 1)
        funding = Block(1, genesis.hash, FAUCET_ID, (reward,), 0, 0)
        for miner in self.network.miners:
            miner.receive_block(funding)
        coin = OutPoint(reward.tx_id, 0)
        self._payment = Transaction(
            (coin,), (TxOutput(self.victim.miner_id, COIN_VALUE),)
        )
        self._refund = Transaction(
            (coin,), (TxOutput(self.attacker.miner_id, COIN_VALUE),)
        )
        for miner in self.honest:
            miner.mempool.append(self._payment)
        self.attacker.mempool.append(self._refund)
        self.attacker.fork_from(funding.hash)
        self._fork_height = funding.index

    def _payment_confirmations(self, miner: Miner) -> int:
        chain = miner.chain.main_chain()
        for block in reversed(chain):
            if self._payment in block.txs:
                return chain[-1].index - block.index + 1
        return 0

    def _confirmed(self) -> bool:
        return self._payment_confirmations(self.attacker) >= self.confirmation_depth

    def _should_release(self) -> bool:
        public_height = self.attacker.chain.tip.index
        return self._confirmed() and self.attacker.should_release(public_height)

    def _should_give_up(self) -> bool:
        lead = self.attacker.chain.tip.index - self.attacker.private.tip.index
        return self._confirmed() and lead > self.give_up_deficit

    def _release(self) -> AttackResult:
        before = {block.hash for block in self.victim.chain.main_chain()}
        blocks = self.attacker.release()
        self.network.publish(self.attacker.miner_id, to_broadcasts(blocks))
        self.network.settle()
        after = {block.hash for block in self.victim.chain.main_chain()}
        return self._result(released=True, reorg_depth=len(before - after))

    def _double_spent(self, main_chain: list[Block]) -> bool:
        confirmed = {tx.tx_id for block in main_chain for tx in block.txs}
        return self._refund.tx_id in confirmed and self._payment.tx_id not in confirmed

    def _result(self, released: bool, reorg_depth: int) -> AttackResult:
        chain: Blockchain = self.victim.chain
        main_chain = chain.main_chain()
        contested = main_chain[self._fork_height + 1 :]
        orphans = len(chain.orphaned_blocks())
        total = len(contested) + orphans
        success = self._double_spent(main_chain)
        rejected = sum(stats.rejections for stats in self.safe_mode_stats) > 0
        return AttackResult(
            attack_success=success,
            private_len=self.attacker.private.tip.index - self._fork_height,
            final_chain_length=chain.tip.index,
            reorg_depth=reorg_depth,
            max_consecutive_by_one_miner=_longest_run(main_chain[1:]),
            blocked_by_safe_mode=self.defense_enabled and rejected and not success,
            orphan_rate=orphans / total if total else 0.0,
            miner_block_counts=dict(Counter(b.miner_id for b in contested)),
            released=released,
        )


def make_scenario(
    attacker_share: float,
    confirmation_depth: int,
    defense_enabled: bool,
    seed: int,
    honest_miners: int = 5,
    max_consecutive: int = 6,
    block_interval: float = 600.0,
    propagation_delay: float = 2.0,
    max_time: float | None = None,
    give_up_deficit: int = DEFAULT_GIVE_UP_DEFICIT,
) -> AttackScenario:
    """Honest miners split the remaining hash power and each runs its own chain,
    protected by the LPC rule when `defense_enabled`."""
    if honest_miners < 1:
        raise ValueError("honest_miners must be at least 1")
    honest_share = (1.0 - attacker_share) / honest_miners
    attacker = MaliciousMiner(ATTACKER_ID, attacker_share)
    honest: list[Miner] = []
    stats: list[SafeModeStats] = []
    for index in range(honest_miners):
        chain, node_stats = build_chain(defense_enabled, max_consecutive)
        honest.append(HonestMiner(f"honest-{index}", honest_share, chain))
        stats.append(node_stats)
    network = Network(
        [attacker, *honest],
        seed=seed,
        block_interval=block_interval,
        propagation_delay=propagation_delay,
    )
    limit = block_interval * DEFAULT_BLOCKS_PER_RUN if max_time is None else max_time
    return AttackScenario(
        network,
        ATTACKER_ID,
        VICTIM_ID,
        confirmation_depth,
        defense_enabled,
        limit,
        give_up_deficit,
        stats,
    )


def _longest_run(blocks: Sequence[Block]) -> int:
    best = run = 0
    previous: str | None = None
    for block in blocks:
        run = run + 1 if block.miner_id == previous else 1
        previous = block.miner_id
        best = max(best, run)
    return best
