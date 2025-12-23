from enum import Enum

class Severity(Enum):
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
    def __init__(self, message: str, severity: Severity, kind: ErrorKind, original_exception: Exception = None):
        super().__init__(message)
        self.severity = severity
        self.kind = kind
        self.original_exception = original_exception