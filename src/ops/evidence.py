import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib

class EvidenceCollector:
    def __init__(self, run_id: str, logs_dir: str = "logs"):
        self.run_id = run_id
        self.logs_dir = Path(logs_dir)
        self.requests_log_path = self.logs_dir / "failed_requests.jsonl"
        self.responses_dir = self.logs_dir / "failed_responses"
        
        # Ensure directories exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def log_failed_request(
        self, 
        method: str, 
        url: str, 
        status_code: int, 
        error_type: str, 
        headers: Dict[str, str], 
        context: Dict[str, Any],
        response_body: Optional[bytes] = None
    ):
        """
        Log failed request metadata to JSONL and save body sample if provided.
        """
        timestamp = datetime.now().isoformat()
        
        # Redact secrets from headers
        safe_headers = {k: v for k, v in headers.items() if 'auth' not in k.lower() and 'key' not in k.lower()}
        
        entry = {
            "timestamp": timestamp,
            "run_id": self.run_id,
            "method": method,
            "full_url": url,
            "status_code": status_code,
            "error_type": error_type,
            "headers": safe_headers,
            "context": context
        }
        
        # Save body sample if available
        if response_body:
            body_hash = hashlib.sha256(response_body).hexdigest()[:16]
            body_sample_path = self.responses_dir / f"{body_hash}.txt"
            entry["body_sample_path"] = str(body_sample_path)
            
            # Save first 2KB
            try:
                with open(body_sample_path, "wb") as f:
                    # If binary, save hex? For now just save raw bytes, it's safer for debug tools.
                    # Or decode safely. Use 'errors=replace' for text view.
                    f.write(response_body[:2048])
                    if len(response_body) > 2048:
                        f.write(b"\n...[TRUNCATED]")
            except Exception as e:
                entry["body_save_error"] = str(e)

        # Append to JSONL
        try:
            with open(self.requests_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"CRITICAL: Failed to write evidence log: {e}")
