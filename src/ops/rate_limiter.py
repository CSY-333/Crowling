import time
import random
import logging
import requests
from ..config import RateLimitConfig

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Manages request delays and provides a reusable session.
    """
    def __init__(self, config: RateLimitConfig):
        self.baseline_min = config.baseline_min_delay
        self.min_delay = config.min_delay
        self.max_delay = config.max_delay
        self.session = requests.Session()
        
        # Ensure max is valid relative to min
        if self.max_delay < self.min_delay:
            self.max_delay = self.min_delay + 1.0

    def wait(self):
        """
        Sleep for a random duration between min_delay and max_delay.
        """
        delay = random.uniform(self.min_delay, self.max_delay)
        if delay > 0:
            time.sleep(delay)

    def update_min_delay(self, new_min: float):
        """
        Update the minimum delay (e.g. from AutoThrottler).
        Automatically adjusts max_delay to maintain the spread.
        """
        self.min_delay = max(0.0, new_min)
        # Maintain the original spread or at least ensure max > min
        spread = max(1.0, self.max_delay - self.baseline_min) 
        self.max_delay = self.min_delay + spread
        
    def close(self):
        self.session.close()