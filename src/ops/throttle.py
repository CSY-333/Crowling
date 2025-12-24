import logging
from collections import deque
from datetime import datetime
from typing import Optional

from ..config import AutoThrottleConfig
from ..storage.db import Database
from .rate_limiter import RateLimiter
from .run_events import RunEventLogger

logger = logging.getLogger(__name__)

class AutoThrottler:
    """
    Monitors response status codes and adjusts RateLimiter delays.
    Implements 429 backoff and 403 emergency stop.
    """
    def __init__(
        self,
        config: AutoThrottleConfig,
        limiter: RateLimiter,
        db: Database,
        run_id: str,
        event_logger: Optional[RunEventLogger] = None,
    ):
        self.config = config
        self.limiter = limiter
        self.db = db
        self.run_id = run_id
        self.event_logger = event_logger
        
        # Sliding window for 429 detection (True if 429, False otherwise)
        self.history = deque(maxlen=config.window)
        
        # Recovery window (longer history)
        self.recovery_history = deque(maxlen=config.recovery_window)
        
        self.is_stopped = False
        self.stop_reason = None

    def observe(self, status_code: int):
        """
        Feed a response status code to the throttler.
        """
        if self.is_stopped:
            return

        # 1. Hard Rule: Stop on 403
        if self.config.stop_on_403 and status_code == 403:
            self._emergency_stop("Received 403 Forbidden")
            return

        # 2. Record history
        is_429 = (status_code == 429)
        self.history.append(is_429)
        self.recovery_history.append(is_429)

        # 3. Check Throttle Up (Window full)
        if len(self.history) == self.history.maxlen:
            ratio_429 = sum(self.history) / len(self.history)
            if ratio_429 > self.config.ratio_429_threshold:
                self._throttle_up(ratio_429)
                # Clear history to avoid rapid-fire step-ups
                self.history.clear() 
                return

        # 4. Check Recovery (Window full)
        if len(self.recovery_history) == self.recovery_history.maxlen:
            ratio_429_rec = sum(self.recovery_history) / len(self.recovery_history)
            if ratio_429_rec < self.config.ratio_429_recovery_threshold:
                # Only recover if we are above baseline
                if self.limiter.min_delay > self.limiter.baseline_min:
                    self._throttle_down(ratio_429_rec)
                    self.recovery_history.clear()

    def _throttle_up(self, ratio: float):
        old_val = self.limiter.min_delay
        new_val = old_val + self.config.min_delay_step_up
        self.limiter.update_min_delay(new_val)
        
        msg = f"Throttle UP: 429 ratio {ratio:.2%} > {self.config.ratio_429_threshold:.2%}. Delay {old_val:.2f}s -> {new_val:.2f}s"
        logger.warning(msg)
        self._log_event("THROTTLE_UP", msg)

    def _throttle_down(self, ratio: float):
        old_val = self.limiter.min_delay
        new_val = max(self.limiter.baseline_min, old_val - self.config.min_delay_step_down)
        
        if new_val != old_val:
            self.limiter.update_min_delay(new_val)
            msg = f"Throttle DOWN: Recovery ratio {ratio:.2%}. Delay {old_val:.2f}s -> {new_val:.2f}s"
            logger.info(msg)
            self._log_event("THROTTLE_DOWN", msg)

    def _emergency_stop(self, reason: str):
        self.is_stopped = True
        self.stop_reason = reason
        logger.critical(f"AutoThrottler triggered STOP: {reason}")
        self._log_event("STOP_LIMIT", reason)
        
    def _log_event(self, event_type: str, details: str):
        if self.event_logger:
            self.event_logger.log(event_type, details)
            return

        try:
            conn = self.db.get_connection()
            with conn:
                conn.execute(
                    "INSERT INTO events (run_id, timestamp, event_type, details) VALUES (?, ?, ?, ?)",
                    (self.run_id, datetime.now().isoformat(), event_type, details),
                )
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log throttle event: {e}")
