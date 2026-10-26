"""
inspector.py — ZiwaVision Active Inspector.

The inspector receives one scene's worth of pre-read band arrays plus a
reference mask and runs a bounded investigation loop.  Instead of making a
single-pass decision it works through a fixed tool menu:

    ACCEPT_FOR_REVIEW          — all deterministic gates pass; add to review queue
    INSPECT_CROP               — re-run detection on a tight crop of the largest patch
    TRY_ALTERNATIVE_ANALYSIS   — repeat detection without GrabCut (pure NDVI+SCL path)
    CHECK_PERSISTENCE          — compare candidate mask overlap with the reference date
    FETCH_ANOTHER_SCENE        — terminate early; ask orchestrator for an adjacent scene
    REQUEST_HUMAN_VERIFICATION — forward to human with full evidence trace

Every round is written as a structured ToolResult.  On exit the full trace is
saved to outputs/traces/<date>.json and a one-line summary appended to
decisions.jsonl.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

import numpy as np

# ── local imports ──────────────────────────────────────────────────────────────
from vision import (
    SceneVision,
    Patch,
    detect_patches,
    PIXEL_HA,
)
from assess import SceneAssessment


# ── deterministic gate thresholds ─────────────────────────────────────────────
# Mirrored from agent.py so both modules stay consistent.
# Logged by name in every trace entry so reviewers see which gate triggered.

GATE_QUALITY_MIN         = 0.70   # image quality must be >= this to proceed
GATE_CONF_HIGH           = 0.55   # confidence >= this + IoU check -> accept
GATE_CONF_LOW            = 0.30   # confidence < this -> suspicious
GATE_IOU_MIN             = 0.05   # IoU vs reference must be >= this to accept
GATE_AREA_MIN_HA         = 0.05   # patches smaller than this are noise
GATE_CROP_CONF_DELTA     = 0.05   # crop re-analysis must shift confidence by >= this
GATE_ALTERNATIVE_AGREE   = 0.70   # GrabCut vs pure-NDVI area agreement fraction
GATE_PERSISTENCE_OVERLAP = 0.10   # candidate-vs-reference pixel overlap to call it persistent
MAX_ROUNDS               = 6      # hard cap on investigation rounds per scene


# ── tool menu ─────────────────────────────────────────────────────────────────

class Tool(str, Enum):
    ACCEPT_FOR_REVIEW          = "accept_for_review"
    INSPECT_CROP               = "inspect_crop"
    TRY_ALTERNATIVE_ANALYSIS   = "try_alternative_analysis"
    CHECK_PERSISTENCE          = "check_persistence"
    FETCH_ANOTHER_SCENE        = "fetch_another_scene"
    REQUEST_HUMAN_VERIFICATION = "request_human_verification"


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    """Structured outcome of running one tool. All numeric fields match what
    OpenCV actually computed so the trace is fully auditable."""
    tool: Tool
    round_index: int
    image_quality:       Optional[float] = None
    cloud_fraction:      Optional[float] = None
    n_patches:           Optional[int]   = None
    total_area_ha:       Optional[float] = None
    mean_confidence:     Optional[float] = None
    scene_iou:           Optional[float] = None
    persistence_overlap: Optional[float] = None
    alternative_agree:   Optional[float] = None
    crop_conf_before:    Optional[float] = None
    crop_conf_after:     Optional[float] = None
    evidence:   str = ""   # must contain actual numbers from OpenCV output
    conclusion: str = ""   # what gate triggered and what it means

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tool"] = self.tool.value
        return d


@dataclass
class InspectionTrace:
    """Full audit record for one scene inspection."""
    scene_id:     str
    date:         str
    location:     str
    bbox:         List[float]
    rounds:       List[ToolResult] = field(default_factory=list)
    final_action: str = ""
    final_reason: str = ""
    human_approved: Optional[bool] = None
    human_note:     Optional[str]  = None
    inspected_at:   str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rounds"] = [r.to_dict() for r in self.rounds]
        return d


# ── tools (pure functions, all return ToolResult) ─────────────────────────────

def _tool_accept_for_review(
    round_idx: int,
    assessment: SceneAssessment,
) -> ToolResult:
    """
    Evaluate all deterministic gates and report whether the detection can be
    accepted for human review.  Every gate reading is included in evidence.
    """
    q    = assessment.image_quality
    conf = assessment.mean_patch_confidence
    iou  = assessment.scene_iou
    area = assessment.total_area_ha
    n    = assessment.n_patches

    gates_pass = (
        q    >= GATE_QUALITY_MIN and
        conf >= GATE_CONF_HIGH   and
        iou  >= GATE_IOU_MIN     and
        area >= GATE_AREA_MIN_HA and
        n    > 0
    )

    evidence = (
        f"quality={q:.3f} (gate>={GATE_QUALITY_MIN}), "
        f"confidence={conf:.3f} (gate>={GATE_CONF_HIGH}), "
        f"iou={iou:.4f} (gate>={GATE_IOU_MIN}), "
        f"area={area:.2f} ha (gate>={GATE_AREA_MIN_HA}), "
        f"n_patches={n}"
    )

    if gates_pass:
        conclusion = (
            "All deterministic gates pass. "
            "Candidate floating vegetation accepted for human review."
        )
    else:
        failing = []
        if q    < GATE_QUALITY_MIN: failing.append(f"quality {q:.3f}<{GATE_QUALITY_MIN}")
        if conf < GATE_CONF_HIGH:   failing.append(f"confidence {conf:.3f}<{GATE_CONF_HIGH}")
        if iou  < GATE_IOU_MIN:     failing.append(f"iou {iou:.4f}<{GATE_IOU_MIN}")
        if area < GATE_AREA_MIN_HA: failing.append(f"area {area:.2f}<{GATE_AREA_MIN_HA} ha")
        if n    == 0:               failing.append("no patches detected")
        conclusion = "Gate(s) failed: " + "; ".join(failing) + ". Not accepted."

    return ToolResult(
        tool=Tool.ACCEPT_FOR_REVIEW,
        round_index=round_idx,
        image_quality=q,
        cloud_fraction=assessment.cloud_fraction,
        n_patches=n,
        total_area_ha=area,
        mean_confidence=conf,
        scene_iou=iou,
        evidence=evidence,
        conclusion=conclusion,
    )


def _tool_inspect_crop(
    round_idx: int,
    largest_patch: Patch,
    red: np.ndarray,
    nir: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    scl: np.ndarray,
    lake_filled: np.ndarray,
) -> ToolResult:
    """
    Re-run full detection on a 20-pixel-padded crop around the largest patch.
    Reports the confidence delta; GrabCut has better context in a tight crop.
    """
    PAD = 20
    r0, c0, r1, c1 = largest_patch.bbox_px
    h, w = red.shape
    r0c = max(0, r0 - PAD);  r1c = min(h, r1 + PAD)
    c0c = max(0, c0 - PAD);  c1c = min(w, c1 + PAD)
    conf_before = largest_patch.confidence

    try:
        sv_crop = detect_patches(
            scene_id="crop", date="crop",
            red        = red        [r0c:r1c, c0c:c1c],
            nir        = nir        [r0c:r1c, c0c:c1c],
            green      = green      [r0c:r1c, c0c:c1c],
            blue       = blue       [r0c:r1c, c0c:c1c],
            scl        = scl        [r0c:r1c, c0c:c1c],
            lake_filled= lake_filled[r0c:r1c, c0c:c1c],
            use_grabcut=True,
        )
        if sv_crop.patches:
            conf_after = max(p.confidence for p in sv_crop.patches)
            area_crop  = sum(p.area_ha for p in sv_crop.patches)
            n_crop     = len(sv_crop.patches)
        else:
            conf_after = 0.0
            area_crop  = 0.0
            n_crop     = 0

    except Exception as exc:
        msg = (
            f"Crop re-analysis failed ({exc}); "
            f"confidence unchanged at {conf_before:.3f}."
        )
        return ToolResult(
            tool=Tool.INSPECT_CROP,
            round_index=round_idx,
            mean_confidence=conf_before,
            crop_conf_before=conf_before,
            crop_conf_after=conf_before,
            evidence=msg,
            conclusion=msg,
        )

    delta = conf_after - conf_before
    evidence = (
        f"Scene-level patch bbox=({r0},{c0}->({r1},{c1})), "
        f"crop window rows {r0c}:{r1c} cols {c0c}:{c1c}. "
        f"crop_patches={n_crop}, crop_area={area_crop:.2f} ha. "
        f"conf_before={conf_before:.3f}, conf_after={conf_after:.3f}, "
        f"delta={delta:+.3f} (threshold={GATE_CROP_CONF_DELTA})"
    )

    if abs(delta) >= GATE_CROP_CONF_DELTA:
        direction = "increased" if delta > 0 else "decreased"
        conclusion = (
            f"Confidence {direction} by {abs(delta):.3f} "
            f"(>= threshold {GATE_CROP_CONF_DELTA}). "
            f"Updated confidence: {conf_after:.3f}."
        )
    else:
        conclusion = (
            f"Delta {delta:+.3f} below threshold {GATE_CROP_CONF_DELTA}. "
            f"Confidence held at {conf_before:.3f}."
        )

    return ToolResult(
        tool=Tool.INSPECT_CROP,
        round_index=round_idx,
        n_patches=n_crop,
        total_area_ha=area_crop,
        mean_confidence=conf_after,
        crop_conf_before=conf_before,
        crop_conf_after=conf_after,
        evidence=evidence,
        conclusion=conclusion,
    )


def _tool_try_alternative_analysis(
    round_idx: int,
    red: np.ndarray,
    nir: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    scl: np.ndarray,
    lake_filled: np.ndarray,
    grabcut_area_ha: float,
) -> ToolResult:
    """
    Run detection WITHOUT GrabCut (pure NDVI + SCL path) and compare
    candidate area to the GrabCut result.  Agreement = min/max of the two
    areas.  High agreement means the signal is not a GrabCut artefact.
    """
    try:
        sv_alt = detect_patches(
            scene_id="alt", date="alt",
            red=red, nir=nir, green=green, blue=blue,
            scl=scl, lake_filled=lake_filled,
            use_grabcut=False,
        )
        alt_area = sum(p.area_ha for p in sv_alt.patches)
        n_alt    = len(sv_alt.patches)
        if alt_area > 0:
            alt_conf = (
                sum(p.confidence * p.area_ha for p in sv_alt.patches) / alt_area
            )
        else:
            alt_conf = 0.0

    except Exception as exc:
        return ToolResult(
            tool=Tool.TRY_ALTERNATIVE_ANALYSIS,
            round_index=round_idx,
            evidence=f"Alternative analysis failed: {exc}",
            conclusion="Alternative analysis unavailable; treating as inconclusive.",
        )

    denom = max(grabcut_area_ha, alt_area, 1e-6)
    agree = min(grabcut_area_ha, alt_area) / denom

    evidence = (
        f"GrabCut area={grabcut_area_ha:.2f} ha, "
        f"pure-NDVI+SCL area={alt_area:.2f} ha ({n_alt} patch(es)), "
        f"agreement={agree:.2%} (gate>={GATE_ALTERNATIVE_AGREE:.0%})"
    )

    if agree >= GATE_ALTERNATIVE_AGREE:
        conclusion = (
            f"Both analyses agree at {agree:.2%} "
            f"(>= {GATE_ALTERNATIVE_AGREE:.0%} threshold). "
            "Detection is internally consistent."
        )
    else:
        conclusion = (
            f"Analyses disagree at {agree:.2%} "
            f"(< {GATE_ALTERNATIVE_AGREE:.0%} threshold). "
            "Candidate area estimate is unreliable."
        )

    return ToolResult(
        tool=Tool.TRY_ALTERNATIVE_ANALYSIS,
        round_index=round_idx,
        n_patches=n_alt,
        total_area_ha=alt_area,
        mean_confidence=round(alt_conf, 3),
        alternative_agree=round(agree, 4),
        evidence=evidence,
        conclusion=conclusion,
    )


def _tool_check_persistence(
    round_idx: int,
    candidate_mask: np.ndarray,
    reference_mask,
) -> ToolResult:
    """
    Measure pixel-level overlap between this date's candidate mask and the
    reference-date vegetation mask.  High overlap = vegetation was present
    on the clearest prior observation too.
    """
    if reference_mask is None or reference_mask.sum() == 0:
        return ToolResult(
            tool=Tool.CHECK_PERSISTENCE,
            round_index=round_idx,
            persistence_overlap=None,
            evidence="No reference mask available; persistence check skipped.",
            conclusion="Persistence could not be assessed (no reference).",
        )

    cand = candidate_mask.astype(bool)
    ref  = reference_mask.astype(bool)

    cand_px    = int(cand.sum())
    overlap_px = int((cand & ref).sum())
    overlap_frac = overlap_px / cand_px if cand_px > 0 else 0.0

    evidence = (
        f"Candidate pixels={cand_px} ({cand_px * PIXEL_HA:.2f} ha), "
        f"overlap with reference={overlap_px} px "
        f"({overlap_px * PIXEL_HA:.2f} ha), "
        f"overlap_fraction={overlap_frac:.4f} "
        f"(gate>={GATE_PERSISTENCE_OVERLAP})"
    )

    if overlap_frac >= GATE_PERSISTENCE_OVERLAP:
        conclusion = (
            f"Persistence confirmed: {overlap_frac:.2%} of candidate pixels "
            "overlap the reference vegetation mask."
        )
    else:
        conclusion = (
            f"Low persistence: overlap_fraction={overlap_frac:.4f} "
            f"< {GATE_PERSISTENCE_OVERLAP} threshold. "
            "Candidate floating vegetation may be new or a false positive."
        )

    return ToolResult(
        tool=Tool.CHECK_PERSISTENCE,
        round_index=round_idx,
        persistence_overlap=round(overlap_frac, 4),
        evidence=evidence,
        conclusion=conclusion,
    )


def _tool_fetch_another_scene(round_idx: int, reason: str) -> ToolResult:
    """
    Signal to the orchestrator that this scene is not useful and a different
    date should be tried.  Performs no computation itself.
    """
    return ToolResult(
        tool=Tool.FETCH_ANOTHER_SCENE,
        round_index=round_idx,
        evidence=reason,
        conclusion=(
            "Inspector terminating early. "
            "Orchestrator should retry with an adjacent observation date."
        ),
    )


def _tool_request_human_verification(
    round_idx: int,
    assessment: SceneAssessment,
    trace: InspectionTrace,
) -> ToolResult:
    """
    Forward the full accumulated evidence to a human reviewer.
    Called when the inspector exhausts the tool menu without a clean answer.
    """
    tools_used = [r.tool.value for r in trace.rounds]
    evidence = (
        f"Inspector ran {len(trace.rounds)} round(s) "
        f"using tools: {tools_used}. "
        f"Final metrics: "
        f"quality={assessment.image_quality:.3f}, "
        f"confidence={assessment.mean_patch_confidence:.3f}, "
        f"iou={assessment.scene_iou:.4f}, "
        f"area={assessment.total_area_ha:.2f} ha, "
        f"n_patches={assessment.n_patches}."
    )
    conclusion = (
        "Inspector could not reach a deterministic accept/reject conclusion. "
        "Full trace forwarded to human reviewer."
    )
    return ToolResult(
        tool=Tool.REQUEST_HUMAN_VERIFICATION,
        round_index=round_idx,
        image_quality=assessment.image_quality,
        n_patches=assessment.n_patches,
        total_area_ha=assessment.total_area_ha,
        mean_confidence=assessment.mean_patch_confidence,
        scene_iou=assessment.scene_iou,
        evidence=evidence,
        conclusion=conclusion,
    )


# ── investigation loop ─────────────────────────────────────────────────────────

def _build_candidate_mask(sv: SceneVision, shape) -> np.ndarray:
    """
    Reconstruct a boolean candidate pixel mask from the SceneVision result
    using patch bounding boxes (same conservative approximation as assess.py).
    """
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    for p in sv.patches:
        r0, c0, r1, c1 = p.bbox_px
        mask[r0:r1, c0:c1] = True
    return mask


def _make_assessment(sv: SceneVision, reference_mask) -> SceneAssessment:
    """Thin wrapper around assess.assess() to avoid code duplication."""
    from assess import assess as _assess
    return _assess(sv, reference_mask)


def _close_trace(
    trace: InspectionTrace,
    final_tool: Tool,
    reason: str,
) -> InspectionTrace:
    """Stamp the final action and wall-clock timestamp on the trace."""
    trace.final_action = final_tool.value
    trace.final_reason = reason
    trace.inspected_at = datetime.now(timezone.utc).isoformat()
    return trace


def inspect(
    scene_id:       str,
    date:           str,
    location:       str,
    bbox:           List[float],
    red:            np.ndarray,
    nir:            np.ndarray,
    green:          np.ndarray,
    blue:           np.ndarray,
    scl:            np.ndarray,
    lake_filled:    np.ndarray,
    reference_mask,
) -> InspectionTrace:
    """
    Active Inspector main loop.

    Investigation strategy (deterministic, no LLM required):

    Round 0 — Initial detection.
        Gate 0-a  quality < GATE_QUALITY_MIN         -> FETCH_ANOTHER_SCENE
        Gate 0-b  no patches detected                -> FETCH_ANOTHER_SCENE
        Gate 0-c  all gates pass on first look       -> ACCEPT_FOR_REVIEW
        Otherwise continue investigating.

    Round 1 — INSPECT_CROP on the largest patch.
        If crop confidence >= GATE_CONF_HIGH
           AND scene_iou >= GATE_IOU_MIN              -> ACCEPT_FOR_REVIEW

    Round 2 — TRY_ALTERNATIVE_ANALYSIS (pure NDVI+SCL, no GrabCut).
        If agreement >= GATE_ALTERNATIVE_AGREE
           AND confidence >= GATE_CONF_HIGH
           AND scene_iou >= GATE_IOU_MIN              -> ACCEPT_FOR_REVIEW

    Round 3 — CHECK_PERSISTENCE vs the reference date.
        If overlap >= GATE_PERSISTENCE_OVERLAP
           AND confidence >= GATE_CONF_LOW            -> ACCEPT_FOR_REVIEW
                                                        (persistence lowers the bar)
        If overlap < GATE_PERSISTENCE_OVERLAP
           AND confidence < GATE_CONF_LOW             -> FETCH_ANOTHER_SCENE

    Round 4 — Exhausted deterministic tools.
        -> REQUEST_HUMAN_VERIFICATION with full trace.

    Every round records actual OpenCV numbers in evidence strings.
    Returns an InspectionTrace with all rounds, the final action, and a
    wall-clock timestamp.
    """
    trace = InspectionTrace(
        scene_id=scene_id, date=date, location=location, bbox=bbox,
    )

    # ── Round 0: initial detection ─────────────────────────────────────────────
    sv         = detect_patches(
        scene_id=scene_id, date=date,
        red=red, nir=nir, green=green, blue=blue,
        scl=scl, lake_filled=lake_filled,
        use_grabcut=True,
    )
    assessment = _make_assessment(sv, reference_mask)

    if assessment.image_quality < GATE_QUALITY_MIN:
        r = _tool_fetch_another_scene(
            0,
            f"Image quality {assessment.image_quality:.3f} < {GATE_QUALITY_MIN} "
            f"(cloud_fraction={assessment.cloud_fraction:.3f}). Scene unusable.",
        )
        trace.rounds.append(r)
        return _close_trace(trace, Tool.FETCH_ANOTHER_SCENE, r.conclusion)

    if assessment.n_patches == 0:
        r = _tool_fetch_another_scene(
            0,
            "No candidate patches detected on initial analysis. "
            "Nothing to investigate — try another date.",
        )
        trace.rounds.append(r)
        return _close_trace(trace, Tool.FETCH_ANOTHER_SCENE, r.conclusion)

    accept0 = _tool_accept_for_review(0, assessment)
    trace.rounds.append(accept0)
    if "accepted" in accept0.conclusion:
        return _close_trace(trace, Tool.ACCEPT_FOR_REVIEW, accept0.conclusion)

    # ── Round 1: crop inspection ───────────────────────────────────────────────
    largest = max(sv.patches, key=lambda p: p.area_ha)
    crop_r  = _tool_inspect_crop(
        1, largest, red, nir, green, blue, scl, lake_filled,
    )
    trace.rounds.append(crop_r)

    run_conf = (
        crop_r.crop_conf_after
        if crop_r.crop_conf_after is not None
        else assessment.mean_patch_confidence
    )

    if run_conf >= GATE_CONF_HIGH and assessment.scene_iou >= GATE_IOU_MIN:
        accept1 = ToolResult(
            tool=Tool.ACCEPT_FOR_REVIEW, round_index=1,
            image_quality=assessment.image_quality,
            n_patches=assessment.n_patches,
            total_area_ha=assessment.total_area_ha,
            mean_confidence=run_conf,
            scene_iou=assessment.scene_iou,
            evidence=(
                f"Crop inspection updated confidence to {run_conf:.3f} "
                f">= {GATE_CONF_HIGH}; iou={assessment.scene_iou:.4f} "
                f">= {GATE_IOU_MIN}."
            ),
            conclusion=(
                f"Confidence raised to {run_conf:.3f} by crop inspection. "
                "Gates re-evaluated: accepted."
            ),
        )
        trace.rounds.append(accept1)
        return _close_trace(trace, Tool.ACCEPT_FOR_REVIEW, accept1.conclusion)

    # ── Round 2: alternative analysis ─────────────────────────────────────────
    alt_r = _tool_try_alternative_analysis(
        2, red, nir, green, blue, scl, lake_filled,
        grabcut_area_ha=assessment.total_area_ha,
    )
    trace.rounds.append(alt_r)

    analyses_agree = (alt_r.alternative_agree or 0.0) >= GATE_ALTERNATIVE_AGREE
    conf_alt = (
        alt_r.mean_confidence
        if alt_r.mean_confidence is not None
        else run_conf
    )

    if analyses_agree and conf_alt >= GATE_CONF_HIGH and assessment.scene_iou >= GATE_IOU_MIN:
        accept2 = ToolResult(
            tool=Tool.ACCEPT_FOR_REVIEW, round_index=2,
            image_quality=assessment.image_quality,
            n_patches=assessment.n_patches,
            total_area_ha=assessment.total_area_ha,
            mean_confidence=conf_alt,
            scene_iou=assessment.scene_iou,
            alternative_agree=alt_r.alternative_agree,
            evidence=(
                f"GrabCut and pure-NDVI+SCL agree at "
                f"{alt_r.alternative_agree:.2%} (>={GATE_ALTERNATIVE_AGREE:.0%}). "
                f"Confidence={conf_alt:.3f}>={GATE_CONF_HIGH}."
            ),
            conclusion=(
                f"Both analyses agree ({alt_r.alternative_agree:.2%}); "
                f"confidence {conf_alt:.3f} >= {GATE_CONF_HIGH}. Accepted."
            ),
        )
        trace.rounds.append(accept2)
        return _close_trace(trace, Tool.ACCEPT_FOR_REVIEW, accept2.conclusion)

    # ── Round 3: persistence check ────────────────────────────────────────────
    cand_mask = _build_candidate_mask(sv, red.shape)
    persist_r = _tool_check_persistence(3, cand_mask, reference_mask)
    trace.rounds.append(persist_r)

    overlap = persist_r.persistence_overlap or 0.0

    if overlap >= GATE_PERSISTENCE_OVERLAP and conf_alt >= GATE_CONF_LOW:
        accept3 = ToolResult(
            tool=Tool.ACCEPT_FOR_REVIEW, round_index=3,
            image_quality=assessment.image_quality,
            n_patches=assessment.n_patches,
            total_area_ha=assessment.total_area_ha,
            mean_confidence=conf_alt,
            scene_iou=assessment.scene_iou,
            persistence_overlap=overlap,
            evidence=(
                f"Persistence overlap={overlap:.2%}>={GATE_PERSISTENCE_OVERLAP:.0%}. "
                f"Confidence={conf_alt:.3f}>={GATE_CONF_LOW} (lowered threshold: "
                "persistence is corroborating evidence)."
            ),
            conclusion=(
                f"Persistence confirmed ({overlap:.2%} overlap); "
                f"confidence {conf_alt:.3f} >= low-bar {GATE_CONF_LOW}. "
                "Accepted for human review with corroborating evidence."
            ),
        )
        trace.rounds.append(accept3)
        return _close_trace(trace, Tool.ACCEPT_FOR_REVIEW, accept3.conclusion)

    if overlap < GATE_PERSISTENCE_OVERLAP and conf_alt < GATE_CONF_LOW:
        r = _tool_fetch_another_scene(
            3,
            f"No persistence (overlap={overlap:.4f}<{GATE_PERSISTENCE_OVERLAP}) "
            f"AND low confidence ({conf_alt:.3f}<{GATE_CONF_LOW}). "
            "Signal too weak across all tools. Requesting new date.",
        )
        trace.rounds.append(r)
        return _close_trace(trace, Tool.FETCH_ANOTHER_SCENE, r.conclusion)

    # ── Round 4: exhausted deterministic tools ────────────────────────────────
    human_r = _tool_request_human_verification(4, assessment, trace)
    trace.rounds.append(human_r)
    return _close_trace(trace, Tool.REQUEST_HUMAN_VERIFICATION, human_r.conclusion)


# ── I/O helpers ───────────────────────────────────────────────────────────────

def save_trace(trace: InspectionTrace, traces_dir: str) -> str:
    """
    Save a full InspectionTrace to outputs/traces/<date>.json.
    Returns the path written.
    """
    os.makedirs(traces_dir, exist_ok=True)
    path = os.path.join(traces_dir, f"{trace.date}.json")
    with open(path, "w") as f:
        json.dump(trace.to_dict(), f, indent=2)
    return path


def log_trace_to_jsonl(trace: InspectionTrace, decisions_path: str) -> None:
    """
    Append a one-line summary to decisions.jsonl in the same format the
    existing API and dashboard already read.
    """
    os.makedirs(os.path.dirname(decisions_path), exist_ok=True)
    summary = {
        "scene_id":         trace.scene_id,
        "date":             trace.date,
        "inspector_action": trace.final_action,
        "inspector_reason": trace.final_reason,
        "n_rounds":         len(trace.rounds),
        "tools_used":       [r.tool.value for r in trace.rounds],
        "inspected_at":     trace.inspected_at,
        "human_approved":   trace.human_approved,
    }
    with open(decisions_path, "a") as f:
        f.write(json.dumps(summary) + "\n")
