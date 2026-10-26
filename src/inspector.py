"""Deterministic Active Inspector loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

try:
    from .tools import (
        AnalyzeEvidence,
        EvidenceStatus,
        QualityEvidence,
        SceneContext,
        assess_quality,
        alt_analysis,
        analyze_scene,
        fetch_alternate_scene,
        inspect_crop,
        request_human_verification,
    )
    from .trace import TraceRecord, append_trace
except ImportError:
    from tools import (
        AnalyzeEvidence,
        EvidenceStatus,
        QualityEvidence,
        SceneContext,
        assess_quality,
        alt_analysis,
        analyze_scene,
        fetch_alternate_scene,
        inspect_crop,
        request_human_verification,
    )
    from trace import TraceRecord, append_trace


@dataclass(frozen=True)
class InspectorConfig:
    """Chosen values, not proven universal thresholds."""

    quality_min: float = 0.70
    lake_ratio_min: float = 0.85
    lake_ratio_max: float = 1.15
    confidence_high: float = 0.55
    confidence_mid: float = 0.30
    implausible_area_fraction: float = 0.20
    analysis_iou_min: float = 0.70
    alternate_ndvi_threshold: float = 0.40


@dataclass
class InspectorState:
    context: SceneContext
    config: InspectorConfig
    analysis: Optional[AnalyzeEvidence] = None
    quality: Optional[QualityEvidence] = None
    crop: Optional[CropEvidence] = None
    alternative: Optional[AlternativeEvidence] = None
    used_dates: List[str] = field(default_factory=list)
    action_history: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Action:
    name: str
    rule: str


def choose_next_action(state: InspectorState) -> Action:
    """Choose one fixed-menu action using only measured evidence."""
    analysis = state.analysis
    quality = state.quality
    if analysis is None or quality is None:
        return Action("analyze_scene", "Initial state has no scene or quality evidence.")
    if quality.image_quality < state.config.quality_min or not quality.stable:
        return Action(
            "fetch_alternate_scene",
            f"quality={quality.image_quality:.3f} or lake ratio={quality.lake_area_ratio:.3f} "
            f"fails chosen gates [{state.config.quality_min:.2f}, "
            f"{state.config.lake_ratio_min:.2f}-{state.config.lake_ratio_max:.2f}].",
        )
    if len(analysis.scene.patches) == 0:
        return Action("no_candidate", "Clear, stable scene has 0 detected patches.")
    area_fraction = (
        analysis.scene.candidate_area_ha / analysis.scene.lake_area_ha
        if analysis.scene.lake_area_ha
        else 1.0
    )
    if area_fraction > state.config.implausible_area_fraction:
        return Action(
            "reject_mask_artifact",
            f"candidate area={analysis.scene.candidate_area_ha:.2f} ha is "
            f"{area_fraction:.3f} of lake area={analysis.scene.lake_area_ha:.2f} ha, "
            f"> {state.config.implausible_area_fraction:.2f}.",
        )
    confidence = analysis.scene.patches[0].confidence
    confidence = sum(p.confidence * p.area_ha for p in analysis.scene.patches) / max(
        analysis.scene.candidate_area_ha, 1e-9
    )
    if confidence < state.config.confidence_mid and state.crop is None:
        return Action("inspect_crop", f"Mean confidence={confidence:.3f} is below mid gate.")
    if state.alternative is None:
        return Action("alt_analysis", "Second thresholded analysis is required before agreement decision.")
    if state.alternative.iou < state.config.analysis_iou_min:
        return Action(
            "request_human_verification",
            f"Alternative analysis IoU={state.alternative.iou:.3f} "
            f"< {state.config.analysis_iou_min:.2f}; analyses disagree.",
        )
    if confidence >= state.config.confidence_high:
        return Action(
            "needs_verification",
            f"Mean confidence={confidence:.3f} and alternative IoU={state.alternative.iou:.3f} "
            "pass chosen agreement gates.",
        )
    if state.crop is None:
        return Action("inspect_crop", f"Mean confidence={confidence:.3f} is mid-range.")
    return Action(
        "request_human_verification",
        f"Confidence={confidence:.3f} remains below high gate after crop; human review required.",
    )


def _numbers(state: InspectorState) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if state.quality:
        result.update({
            "quality": state.quality.image_quality,
            "cloud_fraction": state.quality.cloud_fraction,
            "unclassified_fraction": state.quality.unclassified_fraction,
            "lake_area_ratio": state.quality.lake_area_ratio,
        })
    if state.analysis:
        result.update({
            "candidate_pixels": float(state.analysis.candidate_pixels),
            "candidate_area_ha": state.analysis.scene.candidate_area_ha,
            "n_patches": float(len(state.analysis.scene.patches)),
        })
    if state.alternative:
        result["alternative_iou"] = state.alternative.iou
    return result


def inspect_hotspot(site: SceneContext, dates: Sequence[SceneContext], max_steps: int = 8) -> List[TraceRecord]:
    """Run a bounded inspection loop and persist every step as JSONL."""
    config = InspectorConfig()
    state = InspectorState(context=site, config=config, used_dates=[site.date])
    records: List[TraceRecord] = []
    for step in range(max_steps):
        if state.analysis is None:
            state.analysis = analyze_scene(state.context)
            state.quality = assess_quality(state.context)
        action = choose_next_action(state)
        outcome = ""
        reassessment: Dict[str, object] = _numbers(state)
        if action.name == "analyze_scene":
            outcome = state.analysis.message
        elif action.name == "fetch_alternate_scene":
            fetched = fetch_alternate_scene(state.context, state.used_dates)
            outcome = fetched.message
            if fetched.status == EvidenceStatus.OK:
                replacement = next(s for s in dates if s.date == fetched.selected_date)
                state.context = replacement
                state.used_dates.append(replacement.date)
                state.analysis = None
                state.quality = None
                reassessment = {"next_date": replacement.date, "cloud_fraction": fetched.cloud_fraction}
            else:
                action = Action("request_human_verification", fetched.message)
        elif action.name == "inspect_crop":
            patch = max(state.analysis.scene.patches, key=lambda item: item.area_ha)
            state.crop = inspect_crop(state.context, patch)
            outcome = state.crop.message
            reassessment = {"crop_ndvi_mean": state.crop.ndvi_mean, "distance_to_shore_m": state.crop.distance_to_shore_m}
        elif action.name == "alt_analysis":
            state.alternative = alt_analysis(
                state.context, state.analysis, config.alternate_ndvi_threshold
            )
            outcome = state.alternative.message
            reassessment = {"alternative_iou": state.alternative.iou}
        elif action.name == "request_human_verification":
            human = request_human_verification(state.analysis)
            outcome = human.message
            reassessment = {"pending": human.pending, "candidate_area_ha": human.candidate_area_ha}
        else:
            outcome = action.rule
        record = TraceRecord(
            scene_id=state.context.scene_id,
            date=state.context.date,
            location=state.context.location,
            step=step,
            observation=_numbers(state),
            decision=action.name,
            rule=action.rule,
            outcome=outcome,
            reassessment=reassessment,
        )
        append_trace(record)
        records.append(record)
        state.action_history.append(action.name)
        if action.name in {
            "no_candidate",
            "reject_mask_artifact",
            "needs_verification",
            "request_human_verification",
        }:
            break
    else:
        action = "request_human_verification"
        record = TraceRecord(
            scene_id=state.context.scene_id,
            date=state.context.date,
            location=state.context.location,
            step=max_steps,
            observation=_numbers(state),
            decision=action,
            rule=f"Hard termination after max_steps={max_steps}.",
            outcome="Loop terminated safely without an unbounded retry.",
            reassessment=_numbers(state),
        )
        append_trace(record)
        records.append(record)
    return records
