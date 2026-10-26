"""Deterministic Active Inspector loop."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence

import cv2
import matplotlib.pyplot as plt
import numpy as np

try:
    from .pipeline import (
        box_cloud,
        candidates_mask,
        find_scenes,
        lake_mask,
        ndvi_of,
        read_band,
        read_scl,
        ring,
    )
    from .tools import (
        AnalyzeEvidence,
        CropEvidence,
        AlternativeEvidence,
        EvidenceStatus,
        QualityEvidence,
        SceneContext,
        assess_quality,
        alt_analysis,
        analyze_scene,
        fetch_alternate_scene,
        inspect_crop,
        request_human_verification,
        validate_context_shapes,
    )
    from .trace import TraceRecord, append_trace
    from .vision import detect_patches, image_quality_score
    from .assess import assess
    from .agent import decide
except ImportError:
    from pipeline import (
        box_cloud,
        candidates_mask,
        find_scenes,
        lake_mask,
        ndvi_of,
        read_band,
        read_scl,
        ring,
    )
    from tools import (
        AnalyzeEvidence,
        CropEvidence,
        AlternativeEvidence,
        EvidenceStatus,
        QualityEvidence,
        SceneContext,
        assess_quality,
        alt_analysis,
        analyze_scene,
        fetch_alternate_scene,
        inspect_crop,
        request_human_verification,
        validate_context_shapes,
    )
    from trace import TraceRecord, append_trace
    from vision import detect_patches, image_quality_score
    from assess import assess
    from agent import decide


@dataclass(frozen=True)
class RetryConfig:
    """Configurable retry counts and timing for network and STAC interactions."""
    max_retries: int = 3
    base_delay_s: float = 0.02
    backoff_factor: float = 2.0
    sleep_fn: Any = field(default=None)

    def sleep(self, seconds: float) -> None:
        if self.sleep_fn is not None:
            self.sleep_fn(seconds)
        else:
            time.sleep(seconds)


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
    if quality.lake_pixels == 0 or quality.reference_lake_pixels == 0:
        return Action(
            "fetch_alternate_scene",
            f"Input lake mask is empty or invalid (lake={quality.lake_pixels}px, "
            f"ref={quality.reference_lake_pixels}px); input mask quality gate failed.",
        )
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
        open_w_px = getattr(state.analysis, "open_water_pixels", 0)
        open_w_ha = getattr(state.analysis, "open_water_area_ha", round(open_w_px * 0.01, 2))
        result.update({
            "candidate_pixels": float(state.analysis.candidate_pixels),
            "candidate_area_ha": state.analysis.scene.candidate_area_ha,
            "open_water_pixels": float(open_w_px),
            "open_water_area_ha": float(open_w_ha),
            "n_patches": float(len(state.analysis.scene.patches)),
        })
    if state.alternative:
        result["alternative_iou"] = state.alternative.iou
    return result


def inspect_hotspot(
    site: SceneContext,
    dates: Sequence[SceneContext],
    max_steps: int = 8,
    run_id: Optional[str] = None,
) -> List[TraceRecord]:
    """Run a bounded inspection loop and persist every step as JSONL."""
    if run_id is None:
        run_id = uuid.uuid4().hex[:12]

    config = InspectorConfig()
    state = InspectorState(context=site, config=config, used_dates=[site.date])
    records: List[TraceRecord] = []

    # Validate array dimensions and alignment before analysis
    shape_mismatch = validate_context_shapes(state.context)
    if shape_mismatch is not None:
        rec = TraceRecord(
            run_id=run_id,
            scene_id=state.context.scene_id,
            date=state.context.date,
            location=state.context.location,
            step=0,
            action="validate_shapes",
            attempt=1,
            error_category="shape_mismatch",
            observation=shape_mismatch,
            decision="shape_mismatch",
            rule="Validate array dimensions and alignment before analysis",
            outcome=(
                f"Array shape mismatch in scene {state.context.scene_id}: "
                f"expected {shape_mismatch['expected_shape']}, got mismatches in {list(shape_mismatch.get('mismatches', {}).keys())}. "
                "Incompatible inputs will not be combined or silently resized."
            ),
            reassessment={"status": "shape_mismatch"},
        )
        append_trace(rec)
        records.append(rec)

        # Check if an alternate scene is eligible and has matching shapes
        found_alt = False
        for alt in dates:
            if alt.date not in state.used_dates and validate_context_shapes(alt) is None:
                state.context = alt
                state.used_dates.append(alt.date)
                found_alt = True
                break
        if not found_alt:
            return records

    for step in range(max_steps):
        if state.analysis is None:
            state.analysis = analyze_scene(state.context)
            state.quality = assess_quality(state.context)
        action = choose_next_action(state)
        outcome = ""
        error_category = None
        reassessment: Dict[str, object] = _numbers(state)
        if action.name == "analyze_scene":
            outcome = state.analysis.message
        elif action.name == "fetch_alternate_scene":
            fetched = fetch_alternate_scene(state.context, state.used_dates)
            outcome = fetched.message
            if fetched.status == EvidenceStatus.OK:
                replacement = next((s for s in dates if s.date == fetched.selected_date), None)
                if replacement is not None and validate_context_shapes(replacement) is None:
                    state.context = replacement
                    state.used_dates.append(replacement.date)
                    state.analysis = None
                    state.quality = None
                    reassessment = {"next_date": replacement.date, "cloud_fraction": fetched.cloud_fraction}
                else:
                    action = Action("request_human_verification", fetched.message)
                    error_category = "retries_exhausted"
            else:
                action = Action("request_human_verification", fetched.message)
                error_category = "retries_exhausted"
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
            if state.alternative and state.alternative.iou < state.config.analysis_iou_min:
                error_category = "analysis_disagreement"
        else:
            outcome = action.rule

        record = TraceRecord(
            run_id=run_id,
            scene_id=state.context.scene_id,
            date=state.context.date,
            location=state.context.location,
            step=step,
            action=action.name,
            attempt=1,
            error_category=error_category,
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
            "shape_mismatch",
            "max_steps_reached",
        }:
            break
    else:
        decision = "max_steps_reached"
        record = TraceRecord(
            run_id=run_id,
            scene_id=state.context.scene_id,
            date=state.context.date,
            location=state.context.location,
            step=max_steps,
            action="step_limit_guard",
            attempt=1,
            error_category="max_steps_reached",
            observation=_numbers(state),
            decision=decision,
            rule=f"Hard termination after max_steps={max_steps}.",
            outcome=f"Active Inspector reached maximum step budget ({max_steps}) without resolution; terminated with max_steps_reached.",
            reassessment=_numbers(state),
        )
        append_trace(record)
        records.append(record)
    return records


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def run_live_inspection(
    date: str,
    bbox: Optional[List[float]] = None,
    location: str = "Dunga Beach, Winam Gulf",
    retry_config: Optional[RetryConfig] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute live inspection pipeline against Element84 Earth Search Sentinel-2 data.
    Never substitutes demo data silently if live access fails.
    Returns explicit failure status and persists the evidence and decision trace.
    """
    if bbox is None:
        bbox = [34.73, -0.22, 34.83, -0.12]

    if retry_config is None:
        retry_config = RetryConfig()

    if run_id is None:
        run_id = uuid.uuid4().hex[:12]

    outputs_dir = os.path.join(_ROOT, "outputs")
    overlays_dir = os.path.join(outputs_dir, "overlays")
    os.makedirs(outputs_dir, exist_ok=True)
    os.makedirs(overlays_dir, exist_ok=True)

    step_counter = 0
    trace_records: List[TraceRecord] = []

    # 1. Search catalogue for real scene with bounded exponential retries
    scenes = None
    last_query_error = None
    for attempt in range(1, retry_config.max_retries + 1):
        try:
            scenes = find_scenes(bbox, f"{date}/{date}", max_items=5)
            break
        except Exception as exc:
            last_query_error = exc
            is_final = (attempt == retry_config.max_retries)
            delay = retry_config.base_delay_s * (retry_config.backoff_factor ** (attempt - 1))
            rec = TraceRecord(
                run_id=run_id,
                scene_id="unknown",
                date=date,
                location=location,
                step=step_counter,
                action="find_scenes",
                attempt=attempt,
                error_category="transient_network" if not is_final else "retries_exhausted",
                observation={
                    "attempt": attempt,
                    "max_retries": retry_config.max_retries,
                    "delay_s": delay,
                    "error": str(exc),
                },
                decision="stac_query_retry" if not is_final else "access_failure",
                rule="Bounded retries with exponential backoff for STAC catalogue",
                outcome=(
                    f"STAC catalogue query attempt {attempt}/{retry_config.max_retries} failed: {exc}."
                    + (f" Backing off {delay:.2f}s." if not is_final else " Retries exhausted.")
                ),
                reassessment={"status": "retrying" if not is_final else "access_failure"},
            )
            append_trace(rec)
            trace_records.append(rec)
            step_counter += 1
            if not is_final:
                retry_config.sleep(delay)

    if scenes is None:
        return {
            "ok": False,
            "status": "access_failure",
            "error": f"Earth Search query failed after {retry_config.max_retries} retries: {last_query_error}",
            "traces": [t.to_dict() for t in trace_records],
            "decision": "access_failure",
            "run_id": run_id,
        }

    if not scenes:
        rec = TraceRecord(
            run_id=run_id,
            scene_id="unknown",
            date=date,
            location=location,
            step=step_counter,
            action="find_scenes",
            attempt=1,
            error_category="scene_unavailable",
            observation={"bbox": bbox, "found_scenes": 0},
            decision="access_failure",
            rule="Earth Search catalogue query returned zero covering scenes",
            outcome=f"No Sentinel-2 L2A scene found covering bbox on date {date}.",
            reassessment={"status": "scene_unavailable"},
        )
        append_trace(rec)
        trace_records.append(rec)
        return {
            "ok": False,
            "status": "scene_unavailable",
            "error": f"No Sentinel-2 L2A scene found on Earth Search for date {date} covering specified coordinates.",
            "traces": [t.to_dict() for t in trace_records],
            "decision": "access_failure",
            "run_id": run_id,
        }

    # 2. Iterate candidate scenes to read satellite band assets and validate
    scene = None
    bands_data = None
    lake = None

    for scene_idx, cand_scene in enumerate(scenes):
        cand_assets = getattr(cand_scene, "assets", {})
        missing_asset = None
        for b in ("red", "nir", "green", "blue"):
            if hasattr(cand_scene, "assets") and b not in cand_assets:
                missing_asset = b
                break

        if missing_asset is not None:
            rec = TraceRecord(
                run_id=run_id,
                scene_id=cand_scene.id,
                date=date,
                location=location,
                step=step_counter,
                action=f"read_band_{missing_asset}",
                attempt=1,
                error_category="missing_asset",
                observation={"scene_id": cand_scene.id, "missing_asset": missing_asset},
                decision="asset_read_failure",
                rule="Sentinel-2 L2A asset requirement",
                outcome=f"Required asset '{missing_asset}' is missing from scene {cand_scene.id}.",
                reassessment={"try_next_scene": scene_idx + 1 < len(scenes)},
            )
            append_trace(rec)
            trace_records.append(rec)
            step_counter += 1
            continue

        # Read bands with retry
        cur_bands = {}
        band_read_failed = False

        for b in ("red", "nir", "green", "blue"):
            for attempt in range(1, retry_config.max_retries + 1):
                try:
                    cur_bands[b] = read_band(cand_scene, b, bbox)
                    break
                except Exception as exc:
                    is_final = (attempt == retry_config.max_retries)
                    delay = retry_config.base_delay_s * (retry_config.backoff_factor ** (attempt - 1))
                    if is_final:
                        is_missing = isinstance(exc, (KeyError, FileNotFoundError))
                        rec = TraceRecord(
                            run_id=run_id,
                            scene_id=cand_scene.id,
                            date=date,
                            location=location,
                            step=step_counter,
                            action=f"read_band_{b}",
                            attempt=attempt,
                            error_category="missing_asset" if is_missing else "retries_exhausted",
                            observation={"scene_id": cand_scene.id, "band": b, "error": str(exc)},
                            decision="asset_read_failure",
                            rule="Sentinel-2 asset read with bounded exponential retries",
                            outcome=f"Failed to read band asset '{b}' from scene {cand_scene.id} after {attempt} retries: {exc}",
                            reassessment={"try_next_scene": scene_idx + 1 < len(scenes)},
                        )
                        append_trace(rec)
                        trace_records.append(rec)
                        step_counter += 1
                        band_read_failed = True
                    else:
                        retry_config.sleep(delay)
            if band_read_failed:
                break

        if band_read_failed:
            continue

        try:
            cur_bands["scl"] = read_scl(cand_scene, bbox, cur_bands["red"])
        except Exception as exc:
            rec = TraceRecord(
                run_id=run_id,
                scene_id=cand_scene.id,
                date=date,
                location=location,
                step=step_counter,
                action="read_scl",
                attempt=1,
                error_category="missing_asset" if isinstance(exc, (KeyError, FileNotFoundError)) else "asset_read_failure",
                observation={"scene_id": cand_scene.id, "error": str(exc)},
                decision="asset_read_failure",
                rule="Sentinel-2 SCL layer read",
                outcome=f"Failed to read SCL layer from scene {cand_scene.id}: {exc}",
                reassessment={"try_next_scene": scene_idx + 1 < len(scenes)},
            )
            append_trace(rec)
            trace_records.append(rec)
            step_counter += 1
            continue

        red = cur_bands["red"]
        nir = cur_bands["nir"]
        green = cur_bands["green"]
        blue = cur_bands["blue"]
        scl = cur_bands["scl"]

        # Validate array dimensions and alignment before analysis
        if not (red.shape == nir.shape == green.shape == blue.shape == scl.shape):
            actual_shapes = {
                "red": list(red.shape), "nir": list(nir.shape),
                "green": list(green.shape), "blue": list(blue.shape), "scl": list(scl.shape),
            }
            rec = TraceRecord(
                run_id=run_id,
                scene_id=cand_scene.id,
                date=date,
                location=location,
                step=step_counter,
                action="validate_shapes",
                attempt=1,
                error_category="shape_mismatch",
                observation={"expected_shape": list(red.shape), "actual_shapes": actual_shapes},
                decision="shape_mismatch",
                rule="Validate array dimensions and alignment before analysis",
                outcome=f"Image shape mismatch in scene {cand_scene.id}: expected {list(red.shape)}, got {actual_shapes}. Incompatible inputs will not be combined or silently resized.",
                reassessment={"try_next_scene": scene_idx + 1 < len(scenes)},
            )
            append_trace(rec)
            trace_records.append(rec)
            step_counter += 1
            continue

        # Lake mask segmentation
        cand_cloud = float(box_cloud(scl))
        cand_lake = lake_mask(scl)
        if cand_lake is None:
            rec = TraceRecord(
                run_id=run_id,
                scene_id=cand_scene.id,
                date=date,
                location=location,
                step=step_counter,
                action="lake_segmentation",
                attempt=1,
                error_category="quality_gate_failed",
                observation={"cloud_fraction": cand_cloud},
                decision="lake_mask_failed",
                rule="Lake segmentation from SCL water pixels",
                outcome=f"Water body could not be segmented from SCL (cloud fraction: {cand_cloud:.1%})",
                reassessment={"try_next_scene": scene_idx + 1 < len(scenes)},
            )
            append_trace(rec)
            trace_records.append(rec)
            step_counter += 1
            continue

        scene = cand_scene
        bands_data = cur_bands
        lake = cand_lake
        break

    if scene is None or bands_data is None or lake is None:
        last_rec = trace_records[-1] if trace_records else None
        status = last_rec.decision if last_rec else "asset_read_failure"
        err_msg = last_rec.outcome if last_rec else "Failed to acquire a suitable scene."
        return {
            "ok": False,
            "status": status,
            "error": err_msg,
            "traces": [t.to_dict() for t in trace_records],
            "decision": status,
            "run_id": run_id,
        }

    red = bands_data["red"]
    nir = bands_data["nir"]
    green = bands_data["green"]
    blue = bands_data["blue"]
    scl = bands_data["scl"]

    # 4. Reference lake and reference mask
    ref_lake_path = os.path.join(outputs_dir, "reference_lake.png")
    if os.path.exists(ref_lake_path):
        ref_lake = (cv2.imread(ref_lake_path, cv2.IMREAD_GRAYSCALE) > 0).astype(np.uint8)
    else:
        ref_lake = (lake > 0).astype(np.uint8)

    # Validate reference lake shape
    if ref_lake.shape != red.shape:
        rec = TraceRecord(
            run_id=run_id,
            scene_id=scene.id,
            date=date,
            location=location,
            step=step_counter,
            action="validate_shapes",
            attempt=1,
            error_category="shape_mismatch",
            observation={"expected_shape": list(red.shape), "actual_shapes": {"reference_lake": list(ref_lake.shape)}},
            decision="shape_mismatch",
            rule="Validate array dimensions and alignment before analysis",
            outcome=f"Reference lake shape mismatch: expected {list(red.shape)}, got {list(ref_lake.shape)}.",
            reassessment={"status": "shape_mismatch"},
        )
        append_trace(rec)
        trace_records.append(rec)
        return {
            "ok": False,
            "status": "shape_mismatch",
            "error": f"Reference lake shape {list(ref_lake.shape)} does not match scene bands {list(red.shape)}.",
            "traces": [t.to_dict() for t in trace_records],
            "decision": "shape_mismatch",
            "run_id": run_id,
        }

    ref_mask_path = os.path.join(outputs_dir, "reference_mask.png")
    ref_mask = (
        cv2.imread(ref_mask_path, cv2.IMREAD_GRAYSCALE)
        if os.path.exists(ref_mask_path)
        else None
    )
    if ref_mask is not None and ref_mask.shape != red.shape:
        ref_mask = None  # Do not silently combine incompatible masks

    # 5. Build SceneContext and run Active Inspector loop
    context = SceneContext(
        scene_id=scene.id,
        date=date,
        location=location,
        bbox=bbox,
        red=red,
        nir=nir,
        green=green,
        blue=blue,
        scl=scl,
        lake_filled=lake,
        reference_lake=ref_lake,
        reference_mask=ref_mask,
    )

    hotspot_traces = inspect_hotspot(context, [], max_steps=8, run_id=run_id)
    trace_records.extend(hotspot_traces)

    final_action_name = trace_records[-1].decision if trace_records else "unknown"

    if final_action_name == "max_steps_reached":
        return {
            "ok": False,
            "status": "max_steps_reached",
            "error": f"Active Inspector exceeded maximum allowed steps without resolving.",
            "traces": [t.to_dict() for t in trace_records],
            "decision": "max_steps_reached",
            "run_id": run_id,
        }

    if final_action_name == "shape_mismatch":
        return {
            "ok": False,
            "status": "shape_mismatch",
            "error": "Array shape mismatch detected during inspection.",
            "traces": [t.to_dict() for t in trace_records],
            "decision": "shape_mismatch",
            "run_id": run_id,
        }

    # 6. Extract OpenCV candidate detections & build overlay
    shore_band = ring(ref_lake, inside_px=3, outside_px=5)
    try:
        scene_vision = detect_patches(
            scene_id=scene.id,
            date=date,
            red=red,
            nir=nir,
            green=green,
            blue=blue,
            scl=scl,
            lake_filled=ref_lake,
            shore_band=shore_band,
            use_grabcut=True,
        )
    except AssertionError:
        scene_vision = detect_patches(
            scene_id=scene.id,
            date=date,
            red=red,
            nir=nir,
            green=green,
            blue=blue,
            scl=scl,
            lake_filled=ref_lake,
            shore_band=shore_band,
            use_grabcut=False,
        )

    # Build overlay
    rgb = np.clip(np.dstack([red, green, blue]) / 3000.0, 0, 1)
    refined_mask = candidates_mask(ref_lake, ndvi_of(red, nir), scl)
    overlay = rgb.copy()
    if refined_mask is not None and refined_mask.any():
        overlay[refined_mask] = overlay[refined_mask] * 0.4 + np.array([0.6, 0.6, 0.0])

    overlay_filename = f"{date}.png"
    overlay_path = os.path.join(overlays_dir, overlay_filename)
    plt.imsave(overlay_path, np.clip(overlay, 0, 1))

    # 7. Formulate assessment and decision
    assessment = assess(scene_vision, ref_mask)
    decision = decide(assessment)

    final_reason = trace_records[-1].rule if trace_records else decision.reason

    if final_action_name in ("needs_verification", "request_human_verification"):
        v_status = "needs_review"
        action_type = "request_human_verification"
    elif final_action_name in ("reject_mask_artifact", "rejected_as_artefact"):
        v_status = "rejected_as_artefact"
        action_type = "flag_uncertain"
    elif final_action_name in ("no_candidate", "process_another_observation"):
        v_status = "skipped"
        action_type = "process_another_observation"
    else:
        v_status = "uncertain"
        action_type = "flag_uncertain"

    hotspot_entry = {
        "scene_id": scene.id,
        "date": date,
        "location": location,
        "bbox": bbox,
        "image_quality": round(float(assessment.image_quality), 3),
        "cloud_fraction": round(float(assessment.cloud_fraction), 4),
        "unclassified_fraction": round(float(assessment.unclassified_fraction), 4),
        "n_patches": len(scene_vision.patches),
        "total_area_ha": round(float(scene_vision.candidate_area_ha), 2),
        "open_water_area_ha": round(float(int(refined_mask.sum()) * 0.01), 2) if refined_mask is not None else 0.0,
        "open_water_pixels": int(refined_mask.sum()) if refined_mask is not None else 0,
        "lake_area_ha": round(float(scene_vision.lake_area_ha), 2),
        "mean_patch_confidence": round(float(assessment.mean_patch_confidence), 3),
        "scene_iou": round(float(assessment.scene_iou), 4),
        "mean_patch_iou": round(float(assessment.mean_patch_iou), 4),
        "n_in_reference": int(assessment.n_in_reference),
        "action": action_type,
        "agent_reason": final_reason,
        "verification_status": v_status,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "overlay_path": overlay_path,
        "overlay_filename": overlay_filename,
        "patch_details": assessment.patch_details,
    }

    return {
        "ok": True,
        "hotspot": hotspot_entry,
        "traces": [t.to_dict() for t in trace_records],
        "decision": final_action_name,
        "status": v_status,
        "run_id": run_id,
    }

