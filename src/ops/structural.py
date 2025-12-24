import logging
from enum import Enum
from typing import Dict, Optional

from ..common.errors import AppError, Severity, ErrorKind

logger = logging.getLogger(__name__)


class FailureKind(Enum):
    STRUCTURAL = "STRUCTURAL"
    PARSE = "PARSE"
    SCHEMA = "SCHEMA"
    TRANSIENT = "TRANSIENT"
    DATA = "DATA"


class StructuralError(AppError):
    """
    Fatal error raised when the site structure seems to have changed fundamentally,
    making further collection unsafe or useless.
    """
    def __init__(self, message: str):
        super().__init__(message, Severity.ABORT, ErrorKind.STRUCTURAL)


class StructuralDetector:
    """
    Circuit breaker for structural failures.
    If N consecutive parse/schema errors occur, we assume the site layout has changed
    and we should stop to prevent polluting the dataset with garbage/failures.
    """
    def __init__(self, threshold: int = 10):
        self.threshold = threshold
        self.failure_count = 0

    def record_failure(
        self,
        reason: str,
        *,
        kind: FailureKind,
        context: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Track a failure. Only STRUCTURAL kinds increment and contribute towards circuit break counts.
        """
        if kind == FailureKind.STRUCTURAL:
            self.failure_count += 1

        context_note = f" context={context}" if context else ""
        if kind == FailureKind.STRUCTURAL:
            logger.warning(
                "Structural failure #%d/%d detected (%s): %s%s",
                self.failure_count,
                self.threshold,
                kind.value,
                reason,
                context_note,
            )
        else:
            logger.info("Non-structural failure observed (%s): %s%s", kind.value, reason, context_note)

        if kind == FailureKind.STRUCTURAL and self.failure_count >= self.threshold:
            msg = f"Structural integrity threshold exceeded ({self.failure_count} failures). Reason: {reason}"
            logger.critical(msg)
            raise StructuralError(msg)

    def record_success(self) -> None:
        if self.failure_count > 0:
            logger.info("Structural failure counter reset (was %d).", self.failure_count)
            self.failure_count = 0
