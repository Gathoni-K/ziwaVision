"""JSONL trace records for Active Inspector steps."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_DEFAULT_TRACES_DIR = os.path.join(_ROOT, "outputs", "traces")


@dataclass
class TraceRecord:
    scene_id: str
    date: str
    location: str
    step: int
    observation: Dict[str, Any]
    decision: str
    rule: str
    outcome: str
    reassessment: Dict[str, Any] = field(default_factory=dict)
    written_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    attempt: Optional[int] = None
    error_category: Optional[str] = None
    action: Optional[str] = None

    def __post_init__(self):
        if not self.run_id:
            self.run_id = uuid.uuid4().hex[:12]
        if not self.action:
            self.action = self.decision

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")


def _s3_client():
    import boto3  # noqa: PLC0415
    return boto3.client("s3")


def append_trace(record: TraceRecord, traces_dir: str = _DEFAULT_TRACES_DIR) -> str:
    line = json.dumps(record.to_dict(), sort_keys=True) + "\n"
    os.makedirs(traces_dir, exist_ok=True)
    path = os.path.join(traces_dir, f"{record.date}.jsonl")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)

    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            key = f"traces/{record.date}.jsonl"
            try:
                existing = s3.get_object(Bucket=RESULTS_BUCKET, Key=key)["Body"].read().decode("utf-8")
            except Exception:
                existing = ""
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=key,
                Body=(existing + line).encode("utf-8"),
                ContentType="application/x-ndjson",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"S3 append_trace failed ({exc}); saved locally to {path}")

    return path


def load_traces(date: str, traces_dir: str = _DEFAULT_TRACES_DIR) -> List[Dict[str, Any]]:
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            key = f"traces/{date}.jsonl"
            obj = s3.get_object(Bucket=RESULTS_BUCKET, Key=key)
            lines = obj["Body"].read().decode("utf-8").splitlines()
            records: List[Dict[str, Any]] = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            if records:
                return records
        except Exception:  # noqa: BLE001
            pass

    path = os.path.join(traces_dir, f"{date}.jsonl")
    if not os.path.exists(path):
        return []
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


