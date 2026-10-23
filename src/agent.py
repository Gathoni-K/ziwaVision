"""
agent.py — Stateless rule-based decision agent.

The agent reads a SceneAssessment and returns an AgentDecision:
  • process_another_observation — quality or confidence too low, try another date
  • request_human_verification  — high confidence, consistent with reference
  • flag_uncertain              — ambiguous signal, needs human review

All decisions are appended to outputs/decisions.jsonl (one JSON line per scene).

This is a rule-based agent; it needs no external API, LLM, or network call.
The rules are explicit thresholds chosen from the data exploration
(see run_cloud.py, run_unc.py, run_band.py) and recorded here as design choices,
not proven values.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from assess import SceneAssessment


# ── thresholds (design choices, not proven values) ─────────────────────────────
QUALITY_MIN          = 0.70   # below this → too cloudy, try another date
CONFIDENCE_HIGH      = 0.55   # above this + IoU check → request human verification
CONFIDENCE_LOW       = 0.30   # below this → flag uncertain
REFERENCE_IOU_MIN    = 0.05   # IoU must be at least this to call it reference-consistent
AREA_MIN_HA          = 0.05   # patches smaller than this are ignored by the agent


# ── data class ─────────────────────────────────────────────────────────────────

@dataclass
class AgentDecision:
    """One decision for one scene."""
    scene_id:    str
    date:        str
    action:      str       # one of the three valid actions
    reason:      str
    image_quality:         float
    detection_confidence:  float
    reference_iou:         float
    n_patches:             int
    total_area_ha:         float
    verification_status:   str     # 'needs_review' | 'verified' | 'uncertain' | 'skipped'
    decided_at:            str     # ISO timestamp

    def to_dict(self) -> dict:
        return asdict(self)


VALID_ACTIONS = frozenset([
    "process_another_observation",
    "request_human_verification",
    "flag_uncertain",
])


# ── decision logic ─────────────────────────────────────────────────────────────

def decide(assessment: SceneAssessment) -> AgentDecision:
    """
    Apply the decision rules to a SceneAssessment and return an AgentDecision.

    Rules (evaluated in order):

    1. If image quality < QUALITY_MIN → process_another_observation
       Rationale: a cloudy or shadow-affected scene cannot be trusted.

    2. If no patches detected → process_another_observation
       Rationale: nothing to verify; try a different date.

    3. If detection confidence < CONFIDENCE_LOW → flag_uncertain
       Rationale: the signal is too weak to be meaningful; flag for manual review.

    4. If detection confidence >= CONFIDENCE_HIGH
       AND scene IoU >= REFERENCE_IOU_MIN
       AND total area >= AREA_MIN_HA
       → request_human_verification
       Rationale: strong, spatially consistent signal — worth a human look.

    5. Otherwise → process_another_observation
       Rationale: moderate confidence; a different date may give a clearer picture.
    """
    q    = assessment.image_quality
    conf = assessment.mean_patch_confidence
    iou  = assessment.scene_iou
    area = assessment.total_area_ha
    n    = assessment.n_patches

    if q < QUALITY_MIN:
        action = "process_another_observation"
        reason = (
            f"image quality {q:.2f} is below threshold {QUALITY_MIN} "
            f"(cloud fraction {assessment.cloud_fraction:.1%})"
        )
        status = "skipped"

    elif n == 0:
        action = "process_another_observation"
        reason = "no candidate patches detected in this scene"
        status = "skipped"

    elif conf < CONFIDENCE_LOW:
        action = "flag_uncertain"
        reason = (
            f"detection confidence {conf:.2f} is below threshold {CONFIDENCE_LOW}; "
            f"signal too weak ({n} patch(es), {area:.2f} ha)"
        )
        status = "uncertain"

    elif conf >= CONFIDENCE_HIGH and iou >= REFERENCE_IOU_MIN and area >= AREA_MIN_HA:
        action = "request_human_verification"
        reason = (
            f"high confidence {conf:.2f} (>= {CONFIDENCE_HIGH}), "
            f"scene IoU {iou:.3f} (>= {REFERENCE_IOU_MIN}), "
            f"{n} patch(es) totalling {area:.2f} ha — consistent with reference"
        )
        status = "needs_review"

    else:
        action = "process_another_observation"
        reason = (
            f"moderate confidence {conf:.2f}, scene IoU {iou:.3f}, "
            f"{area:.2f} ha — try another observation date for a clearer reading"
        )
        status = "skipped"

    return AgentDecision(
        scene_id=assessment.scene_id,
        date=assessment.date,
        action=action,
        reason=reason,
        image_quality=assessment.image_quality,
        detection_confidence=assessment.mean_patch_confidence,
        reference_iou=assessment.scene_iou,
        n_patches=assessment.n_patches,
        total_area_ha=assessment.total_area_ha,
        verification_status=status,
        decided_at=datetime.now(timezone.utc).isoformat(),
    )


# ── log writer ─────────────────────────────────────────────────────────────────

def log_decision(decision: AgentDecision, log_path: str) -> None:
    """Append a decision as a JSON line to the decisions log."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(decision.to_dict()) + "\n")


# ── human verification update ──────────────────────────────────────────────────

def apply_verification(
    results: list,
    date: str,
    patch_id: Optional[int],
    verified: bool,
    status: Optional[str] = None,
) -> list:
    """
    Update verification_status in the results list for a given date.
    Called by the API when a human clicks Verify, Flag Uncertain, or Reject.

    `results` is the list of dicts from results.json.
    Returns the updated list.
    """
    if status is not None:
        new_status = status
    else:
        new_status = "verified" if verified else "uncertain"
    for entry in results:
        if entry.get("date") == date:
            entry["verification_status"] = new_status
            entry["verified_at"] = datetime.now(timezone.utc).isoformat()
            if patch_id is not None:
                for pd in entry.get("patch_details", []):
                    if pd.get("patch_id") == patch_id:
                        pd["verified"] = verified
    return results
