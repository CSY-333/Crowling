import pytest
from unittest.mock import Mock
from src.ops.structural import StructuralDetector, StructuralError
from src.common.errors import AppError, Severity, ErrorKind

class TestStructuralDetector:
    def test_circuit_opens_after_threshold(self):
        """Should raise StructuralError after N consecutive failures."""
        detector = StructuralDetector(threshold=3)
        
        # 1st failure
        detector.record_failure("Schema mismatch")
        assert detector.failure_count == 1
        
        # 2nd failure
        detector.record_failure("JSONP Parse error")
        assert detector.failure_count == 2
        
        # 3rd failure -> Boom
        with pytest.raises(StructuralError) as exc:
            detector.record_failure("Final failure")
        
        assert exc.value.kind == ErrorKind.STRUCTURAL
        assert exc.value.severity == Severity.ABORT
        assert "threshold exceeded" in str(exc.value)

    def test_circuit_resets_on_success(self):
        """Should reset counter on successful operation."""
        detector = StructuralDetector(threshold=3)
        
        detector.record_failure("Fail 1")
        detector.record_failure("Fail 2")
        assert detector.failure_count == 2
        
        detector.record_success()
        assert detector.failure_count == 0

    def test_record_failure_only_counts_structural_errors(self):
        """Optional: ensure we only count specifically flagged errors if we want selective logic.
           For now, the record_failure method is explicit."""
        pass 
