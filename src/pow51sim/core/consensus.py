from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pow51sim.core.block import Block

if TYPE_CHECKING:
    from pow51sim.core.blockchain import Blockchain


class InvalidBlockError(Exception):
    pass


class ConsensusRule(ABC):
    @abstractmethod
    def validate(self, block: Block, chain: "Blockchain") -> None:
        """Raise InvalidBlockError if the block must be rejected."""
