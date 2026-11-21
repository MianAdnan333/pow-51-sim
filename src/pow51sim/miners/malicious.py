from pow51sim.core.block import Block
from pow51sim.core.blockchain import Blockchain
from pow51sim.core.rules import default_rules
from pow51sim.defense.confirmations import is_confirmed
from pow51sim.miners.base import Miner
from pow51sim.miners.receiver import BlockReceiver


class MaliciousMiner(Miner):
    """Mines a private fork, released once it overtakes the confirmed public chain.

    `public` is the miner's view of the honest chain; `chain` is the private fork.
    After release it behaves like an honest miner.
    """

    def __init__(
        self,
        miner_id: str,
        hash_power: float,
        public: Blockchain,
        fork_height: int = 0,
        confirmations: int = 0,
    ) -> None:
        private = public.copy(rules=default_rules())
        super().__init__(miner_id, hash_power, private)
        self.public = public
        self.fork_height = fork_height
        self.confirmations = confirmations
        self.released = False
        self._public_receiver = BlockReceiver(public)

    def lead_over(self, public: Blockchain) -> int:
        return self.chain.height - public.height

    def receive(self, block: Block) -> list[Block]:
        if self.released:
            self._receiver.submit(block)
            return []
        self._public_receiver.submit(block)
        return self._release_if_ready()

    def _on_mined(self, block: Block) -> list[Block]:
        if self.released:
            return [block]
        return self._release_if_ready()

    def _release_if_ready(self) -> list[Block]:
        if self.lead_over(self.public) <= 0:
            return []
        if not is_confirmed(self.public, self.fork_height, self.confirmations):
            return []
        self.released = True
        return self.chain.main_chain()[self.fork_height + 1 :]
