"""JSONL trace records for Active Inspector steps."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def append_trace(record: TraceRecord, traces_dir: str = "outputs/traces") -> str:
    os.makedirs(traces_dir, exist_ok=True)
    path = os.path.join(traces_dir, f"{record.date}.jsonl")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return path
