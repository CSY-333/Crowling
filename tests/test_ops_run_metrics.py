from src.ops.run_metrics import compute_tier_outcome, compute_health_score


def test_compute_tier_outcome():
    status, note = compute_tier_outcome(total_comments=6000, target_comments=5000, minimum_comments=3000)
    assert status == "A"
    assert "target" in note

    status, note = compute_tier_outcome(total_comments=3500, target_comments=5000, minimum_comments=3000)
    assert status == "B"

    status, note = compute_tier_outcome(total_comments=1000, target_comments=5000, minimum_comments=3000)
    assert status == "C"


def test_compute_health_score_penalties():
    score, flag = compute_health_score(
        duplicate_rate=0.2,
        timestamp_anomalies=2,
        total_mismatch=True,
    )
    assert score < 100
    assert flag is True
