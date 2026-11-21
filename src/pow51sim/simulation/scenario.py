from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from pow51sim.analysis.metrics import longest_run
from pow51sim.core.block import GENESIS, Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.consensus import ConsensusRule, InvalidBlockError
from pow51sim.core.rules import UtxoRule
from pow51sim.core.transaction import OutPoint, Transaction, TxOutput
from pow51sim.defense.confirmations import is_confirmed
from pow51sim.miners.base import Miner
from pow51sim.miners.honest import HonestMiner
from pow51sim.miners.malicious import MaliciousMiner
from pow51sim.miners.selection import Chooser, pick_winner
from pow51sim.simulation.config import AttackConfig

COIN_VALUE = 50


@dataclass(frozen=True)
class AttackResult:
    success: bool
    rounds: int
    reorg_depth: int
    private_chain_length: int
    final_chain_length: int
    max_consecutive_by_one_miner: int
    orphaned_blocks: int
    total_blocks: int
    attacker_blocks: int
    honest_blocks: int
    top_honest_blocks: int


class AttackScenario:
    """Double-spend race between honest miners and one malicious miner.

    The malicious miner owns one coin. It pays the victim on the public chain, while
    its private fork spends the same coin back to itself. The fork is released once
    the payment has enough confirmations and the fork is longer than the public chain.
    """

    def __init__(
        self, config: AttackConfig, rules: Sequence[ConsensusRule], chooser: Chooser
    ) -> None:
        self.config = config
        self.chooser = chooser
        self.public = Blockchain([*rules, UtxoRule()])
        coin = self._fund_attacker()
        self.payment = Transaction((coin,), (TxOutput("victim", COIN_VALUE),))
        self.refund = Transaction((coin,), (TxOutput("malicious", COIN_VALUE),))
        self.attacker = MaliciousMiner(
            "malicious",
            config.attacker_share,
            self.public,
            fork_height=self.public.height,
            confirmations=config.confirmations,
        )
        self.honest_miners = self._build_honest_miners()
        self._miners: list[Miner] = [self.attacker, *self.honest_miners]
        self._payment_pending = True
        self._refund_pending = True

    def run(self) -> AttackResult:
        for round_no in range(1, self.config.max_rounds + 1):
            winner = pick_winner(self._miners, self.chooser)
            released = self._mine(winner, round_no)
            if released:
                return self._result(round_no, self._publish(released))
            if self._should_give_up():
                return self._result(round_no, 0)
        return self._result(self.config.max_rounds, 0)

    def _fund_attacker(self) -> OutPoint:
        funding = Transaction((), (TxOutput("malicious", COIN_VALUE),))
        self.public.add_block(GENESIS.child("funder", 0, txs=(funding,)))
        return OutPoint(funding.tx_id, 0)

    def _build_honest_miners(self) -> list[HonestMiner]:
        count = self.config.honest_miners
        share = (1 - self.config.attacker_share) / count
        ids = ["honest"] if count == 1 else [f"honest-{i}" for i in range(count)]
        return [HonestMiner(miner_id, share, self.public) for miner_id in ids]

    def _mine(self, winner: Miner, round_no: int) -> list[Block]:
        if winner is self.attacker:
            txs = (self.refund,) if self._refund_pending else ()
            self._refund_pending = False
            return self.attacker.mine(round_no, txs)
        txs = (self.payment,) if self._payment_pending else ()
        mined = winner.mine(round_no, txs)
        if not mined:
            return []
        self._payment_pending = False
        return self.attacker.receive(mined[0])

    def _publish(self, released: list[Block]) -> int:
        depth = 0
        try:
            for block in released:
                depth = max(depth, self.public.add_block(block).reorg_depth)
        except InvalidBlockError:
            return 0
        return depth

    def _should_give_up(self) -> bool:
        confirmed = is_confirmed(
            self.public, self.attacker.fork_height, self.config.confirmations
        )
        deficit = -self.attacker.lead_over(self.public)
        return confirmed and deficit > self.config.give_up_deficit

    def _double_spent(self) -> bool:
        confirmed = {tx for block in self.public.main_chain() for tx in block.txs}
        return self.refund in confirmed and self.payment not in confirmed

    def _result(self, rounds: int, reorg_depth: int) -> AttackResult:
        fork_height = self.attacker.fork_height
        private_length = self.attacker.chain.height - fork_height
        main_chain = self.public.main_chain()
        contested = main_chain[fork_height + 1 :]
        total_blocks = len(self.public) - (fork_height + 1)
        by_miner = Counter(block.miner_id for block in contested)
        attacker_blocks = by_miner.pop(self.attacker.miner_id, 0)
        return AttackResult(
            success=self._double_spent(),
            rounds=rounds,
            reorg_depth=reorg_depth,
            private_chain_length=private_length,
            final_chain_length=self.public.height,
            max_consecutive_by_one_miner=longest_run(main_chain[1:]),
            orphaned_blocks=total_blocks - len(contested),
            total_blocks=total_blocks,
            attacker_blocks=attacker_blocks,
            honest_blocks=sum(by_miner.values()),
            top_honest_blocks=max(by_miner.values(), default=0),
        )
