from typing import Tuple


def compute_tier_outcome(total_comments: int, target_comments: int, minimum_comments: int) -> Tuple[str, str]:
    if total_comments >= target_comments:
        return "A", "target_met"
    if total_comments >= minimum_comments:
        return "B", "minimum_met"
    return "C", "below_minimum"


def compute_health_score(
    duplicate_rate: float = 0.0,
    timestamp_anomalies: int = 0,
    total_mismatch: bool = False,
) -> Tuple[int, bool]:
    score = 100
    score -= int(min(max(duplicate_rate, 0.0), 1.0) * 40)
    score -= min(timestamp_anomalies * 5, 20)
    if total_mismatch:
        score -= 30
    score = max(0, score)
    return score, score < 70
