import pytest
from unittest.mock import Mock
from src.ops.volume_strategy import FixedTargetStrategy, VolumeDecision
from src.common.errors import AppError

class TestFixedTargetStrategy:
    def test_should_continue_below_target(self):
        strategy = FixedTargetStrategy(target_comments=100)
        # 50 collected < 100 target
        decision = strategy.decide(current_volume=50, elapsed_seconds=10)
        assert decision.should_stop is False
    
    def test_should_stop_at_target(self):
        strategy = FixedTargetStrategy(target_comments=100)
        # 100 collected == 100 target
        decision = strategy.decide(current_volume=100, elapsed_seconds=10)
        assert decision.should_stop is True
        assert decision.reason == "TARGET_REACHED"

    def test_should_stop_above_target(self):
        strategy = FixedTargetStrategy(target_comments=100)
        # 150 > 100
        decision = strategy.decide(current_volume=150, elapsed_seconds=10)
        assert decision.should_stop is True

class TestVolumeDecision:
    def test_decision_attributes(self):
        decision = VolumeDecision(should_stop=True, reason="LIMIT")
        assert decision.should_stop
        assert decision.reason == "LIMIT"

from src.ops.volume import VolumeTracker

class TestVolumeTracker:
    def test_trimmed_mean_calculation(self):
        tracker = VolumeTracker()
        # 0, 10, 100, 1000
        for c in [0, 10, 100, 1000]:
            tracker.add_count(c)
        
        # Mean of 0, 10, 100, 1000 = 277.5
        # Trimmed mean (if implemented correctly) should act differently if count >= 5
        # With < 5 items, it might just be mean.
        # Let's check implementation behavior:
        # "max(1, int(len*0.2)) if len >= 5 else 0"
        # So for 4 items, trim=0. Mean = 277.5
        assert tracker.current_trimmed_mean() == 277.5

    def test_trimmed_mean_with_outliers(self):
        tracker = VolumeTracker()
        # 5 items: 1, 2, 3, 4, 1000
        # trim = max(1, int(1)) = 1
        # sorted: 1, 2, 3, 4, 1000
        # trimmed: [2, 3, 4] -> sum 9 / 3 = 3.0
        counts = [1, 2, 3, 4, 1000]
        for c in counts:
            tracker.add_count(c)
            
        assert tracker.current_trimmed_mean() == 3.0

    def test_should_expand_logic(self):
        tracker = VolumeTracker()
        # Mean = 10
        tracker.add_count(10)
        tracker.add_count(10)
        
        # Target 100, Collected 50. Remaining needed = 50.
        # Mean yield = 10. Required articles = 50/10 = 5.
        
        # Case 1: Remaining capacity 2. 5 > 2 -> Should Expand = True
        assert tracker.should_expand(
            target_comments=100, 
            collected_comments=50, 
            remaining_capacity=2
        ) is True
        
        # Case 2: Remaining capacity 10. 5 < 10 -> Should Expand = False
        assert tracker.should_expand(
            target_comments=100, 
            collected_comments=50, 
            remaining_capacity=10
        ) is False
