import math
from typing import List, Optional


class VolumeTracker:
    """
    Tracks comment counts per article and advises when to expand the search pool
    using a trimmed-mean estimator (P20-P80).
    """

    def __init__(self):
        self._counts: List[int] = []

    def add_count(self, count: int) -> None:
        self._counts.append(max(0, count))

    def current_trimmed_mean(self) -> float:
        if not self._counts:
            return 0.0
        sorted_counts = sorted(self._counts)
        trim = max(1, int(len(sorted_counts) * 0.2)) if len(sorted_counts) >= 5 else 0
        if trim and len(sorted_counts) > 2 * trim:
            trimmed = sorted_counts[trim : len(sorted_counts) - trim]
        else:
            trimmed = sorted_counts
        return sum(trimmed) / len(trimmed) if trimmed else 0.0

    def estimate_remaining_articles(self, target_comments: int, collected_comments: int) -> Optional[int]:
        remaining = max(0, target_comments - collected_comments)
        if remaining == 0:
            return 0
        mean = self.current_trimmed_mean()
        if mean <= 0:
            return None
        return math.ceil(remaining / mean)

    def should_expand(self, target_comments: int, collected_comments: int, remaining_capacity: int) -> bool:
        estimate = self.estimate_remaining_articles(target_comments, collected_comments)
        if estimate is None:
            return False
        return estimate > remaining_capacity
