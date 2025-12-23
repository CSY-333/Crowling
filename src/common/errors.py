from enum import Enum
from typing import Optional


class Severity(Enum):
    INFO = "INFO"
    WARN = "WARN"
    RETRY = "RETRY"
    ABORT = "ABORT"


class ErrorKind(Enum):
    HTTP = "HTTP"
    PARSE = "PARSE"
    SCHEMA = "SCHEMA"
    STRUCTURAL = "STRUCTURAL"
    UNKNOWN = "UNKNOWN"


class AppError(Exception):
    """
    Domain-specific error that carries severity + classification metadata so
    callers can decide how to recover.
    """

    def __init__(
        self,
        message: str,
        severity: Severity = Severity.WARN,
        kind: ErrorKind = ErrorKind.UNKNOWN,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.kind = kind
        self.original_exception = original_exception

    def __str__(self) -> str:
        base = super().__str__()
        return f"[{self.severity.name}/{self.kind.name}] {base}"
