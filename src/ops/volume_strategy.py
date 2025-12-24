from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

@dataclass
class VolumeDecision:
    should_stop: bool
    reason: Optional[str] = None

class IVolumeStrategy(ABC):
    @abstractmethod
    def decide(self, current_volume: int, elapsed_seconds: float) -> VolumeDecision:
        pass

class FixedTargetStrategy(IVolumeStrategy):
    def __init__(self, target_comments: int):
        self.target_comments = target_comments

    def decide(self, current_volume: int, elapsed_seconds: float) -> VolumeDecision:
        if current_volume >= self.target_comments:
            return VolumeDecision(should_stop=True, reason="TARGET_REACHED")
        return VolumeDecision(should_stop=False)
