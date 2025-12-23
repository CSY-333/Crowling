import json
from pathlib import Path

from src.ops.evidence import EvidenceCollector


def test_log_failed_request_writes_jsonl_and_body(tmp_path):
    logs_dir = tmp_path / "logs"
    collector = EvidenceCollector(run_id="test", logs_dir=str(logs_dir))

    collector.log_failed_request(
        method="GET",
        url="https://example.com",
        status_code=500,
        error_type="HTTP_ERROR",
        headers={"Authorization": "secret", "User-Agent": "pytest"},
        context={"oid": "1"},
        response_body=b"failure body",
    )

    log_path = logs_dir / "failed_requests.jsonl"
    assert log_path.exists()

    data = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert data["run_id"] == "test"
    assert data["status_code"] == 500
    assert "Authorization" not in data["headers"]
    assert data["headers"]["User-Agent"] == "pytest"

    body_path = Path(data["body_sample_path"])
    assert body_path.exists()
    assert body_path.read_bytes().startswith(b"failure body")
