from src.common.errors import AppError, Severity, ErrorKind


def test_app_error_includes_metadata_in_str():
    err = AppError("boom", Severity.ABORT, ErrorKind.HTTP)
    message = str(err)
    assert "ABORT" in message and "HTTP" in message
    assert err.severity is Severity.ABORT
    assert err.kind is ErrorKind.HTTP
