"""Typed, deterministic tools used by the Active Inspector."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

try:
    from .pipeline import box_cloud, ndvi_of, ring
    from .vision import Patch, SceneVision, detect_patches, image_quality_score
except ImportError:
    from pipeline import box_cloud, ndvi_of, ring
    from vision import Patch, SceneVision, detect_patches, image_quality_score


class EvidenceStatus(str, Enum):
    OK = "ok"
    SKIPPED = "skipped"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


@dataclass
class SceneContext:
    scene_id: str
    date: str
    location: str
    bbox: List[float]
    red: np.ndarray
    nir: np.ndarray
    green: np.ndarray
    blue: np.ndarray
    scl: np.ndarray
    lake_filled: np.ndarray
    reference_lake: np.ndarray
    reference_mask: Optional[np.ndarray] = None
    alternate_scenes: Sequence["SceneContext"] = field(default_factory=tuple)


def validate_context_shapes(context: SceneContext) -> Optional[Dict[str, Any]]:
    """
    Validate array dimensions and alignment before analysis.
    Returns None if shapes match; returns a mismatch summary dict if incompatible.
    """
    if not hasattr(context.red, "shape"):
        return {"error": "context.red has no shape attribute"}

    expected_shape = tuple(context.red.shape)
    shapes = {
        "red": tuple(context.red.shape) if hasattr(context.red, "shape") else None,
        "nir": tuple(context.nir.shape) if hasattr(context.nir, "shape") else None,
        "green": tuple(context.green.shape) if hasattr(context.green, "shape") else None,
        "blue": tuple(context.blue.shape) if hasattr(context.blue, "shape") else None,
        "scl": tuple(context.scl.shape) if hasattr(context.scl, "shape") else None,
        "lake_filled": tuple(context.lake_filled.shape) if hasattr(context.lake_filled, "shape") else None,
        "reference_lake": tuple(context.reference_lake.shape) if hasattr(context.reference_lake, "shape") else None,
    }
    if context.reference_mask is not None:
        shapes["reference_mask"] = tuple(context.reference_mask.shape) if hasattr(context.reference_mask, "shape") else None

    mismatches = {name: s for name, s in shapes.items() if s != expected_shape}
    if mismatches:
        return {
            "expected_shape": list(expected_shape),
            "actual_shapes": {k: list(v) if v is not None else None for k, v in shapes.items()},
            "mismatches": {k: list(v) if v is not None else None for k, v in mismatches.items()},
        }
    return None


@dataclass
class AnalyzeEvidence:
    status: EvidenceStatus
    scene: SceneVision
    candidate_mask: np.ndarray
    candidate_pixels: int
    open_water_pixels: int
    message: str
    open_water_area_ha: float = 0.0
    patch_area_ha: float = 0.0
    patch_pixels: int = 0


@dataclass
class QualityEvidence:
    status: EvidenceStatus
    cloud_fraction: float
    unclassified_fraction: float
    image_quality: float
    lake_pixels: int
    reference_lake_pixels: int
    lake_area_ratio: float
    stable: bool
    message: str


@dataclass
class CropEvidence:
    status: EvidenceStatus
    patch_id: Optional[int]
    crop_shape: List[int]
    ndvi_min: float
    ndvi_mean: float
    ndvi_max: float
    distance_to_shore_m: float
    candidate_pixels: int
    message: str


@dataclass
class AlternativeEvidence:
    status: EvidenceStatus
    threshold: float
    first_pixels: int
    alternate_pixels: int
    intersection_pixels: int
    union_pixels: int
    iou: float
    message: str


@dataclass
class FetchEvidence:
    status: EvidenceStatus
    selected_date: Optional[str]
    selected_scene_id: Optional[str]
    remaining_scene_count: int
    cloud_fraction: Optional[float]
    message: str


@dataclass
class HumanEvidence:
    status: EvidenceStatus
    pending: bool
    candidate_pixels: int
    candidate_area_ha: float
    message: str
    open_water_pixels: int = 0
    open_water_area_ha: float = 0.0
    patch_pixels: int = 0
    patch_area_ha: float = 0.0


def _open_water(lake: np.ndarray, erosion_px: int = 7) -> np.ndarray:
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * erosion_px + 1, 2 * erosion_px + 1)
    )
    binary_lake = (lake > 0).astype(np.uint8)
    return cv2.erode(binary_lake, kernel) == 1


def analyze_scene(context: SceneContext) -> AnalyzeEvidence:
    shore_band = ring(context.reference_lake, inside_px=3, outside_px=5)
    detector_note = "GrabCut completed."
    try:
        scene = detect_patches(
            scene_id=context.scene_id,
            date=context.date,
            red=context.red,
            nir=context.nir,
            green=context.green,
            blue=context.blue,
            scl=context.scl,
            lake_filled=context.reference_lake,
            shore_band=shore_band,
            use_grabcut=True,
        )
    except AssertionError as exc:
        detector_note = (
            f"GrabCut invariant failed ({exc}); reran without GrabCut "
            "to keep the evidence domain-constrained."
        )
        scene = detect_patches(
            scene_id=context.scene_id,
            date=context.date,
            red=context.red,
            nir=context.nir,
            green=context.green,
            blue=context.blue,
            scl=context.scl,
            lake_filled=context.reference_lake,
            shore_band=shore_band,
            use_grabcut=False,
        )
    open_water = _open_water(context.reference_lake)
    mask = open_water & (
        (ndvi_of(context.red, context.nir) > 0.30) | (context.scl == 4)
    )
    open_w_px = int(mask.sum())
    open_w_ha = round(open_w_px * 0.01, 2)
    patch_ha = round(float(scene.candidate_area_ha), 2)
    patch_px = int(round(patch_ha / 0.01))
    return AnalyzeEvidence(
        status=EvidenceStatus.OK,
        scene=scene,
        candidate_mask=mask,
        candidate_pixels=patch_px if patch_px > 0 else open_w_px,
        open_water_pixels=open_w_px,
        open_water_area_ha=open_w_ha,
        patch_area_ha=patch_ha,
        patch_pixels=patch_px,
        message=(
            f"OpenCV detected {len(scene.patches)} patch(es), "
            f"{patch_px} connected patch pixels ({patch_ha:.2f} ha; "
            f"open-water core: {open_w_px} px / {open_w_ha:.2f} ha). "
            f"{detector_note}"
        ),
    )


def assess_quality(context: SceneContext) -> QualityEvidence:
    quality, cloud, unclassified = image_quality_score(context.scl)
    current_pixels = int((context.lake_filled > 0).sum())
    reference_pixels = int((context.reference_lake > 0).sum())
    ratio = current_pixels / reference_pixels if reference_pixels else 0.0
    stable = (0.85 <= ratio <= 1.15) if (reference_pixels > 0 and current_pixels > 0) else False
    status = EvidenceStatus.OK if (reference_pixels > 0 and current_pixels > 0) else EvidenceStatus.UNAVAILABLE
    msg = (
        f"cloud={cloud:.4f}, unclassified={unclassified:.4f}, "
        f"quality={quality:.3f}, lake={current_pixels}px, "
        f"reference={reference_pixels}px, ratio={ratio:.3f}."
    )
    if current_pixels == 0 or reference_pixels == 0:
        msg = f"Empty lake mask ({current_pixels}px current, {reference_pixels}px reference); " + msg
    return QualityEvidence(
        status=status,
        cloud_fraction=float(cloud),
        unclassified_fraction=float(unclassified),
        image_quality=float(quality),
        lake_pixels=current_pixels,
        reference_lake_pixels=reference_pixels,
        lake_area_ratio=ratio,
        stable=stable,
        message=msg,
    )


def inspect_crop(context: SceneContext, patch: Patch) -> CropEvidence:
    r0, c0, r1, c1 = patch.bbox_px
    pad = 10
    r0, c0 = max(0, r0 - pad), max(0, c0 - pad)
    r1, c1 = min(context.red.shape[0], r1 + pad), min(context.red.shape[1], c1 + pad)
    crop_ndvi = ndvi_of(context.red[r0:r1, c0:c1], context.nir[r0:r1, c0:c1])
    crop_mask = _open_water(context.reference_lake)[r0:r1, c0:c1] & (crop_ndvi > 0.30)
    return CropEvidence(
        status=EvidenceStatus.OK,
        patch_id=patch.patch_id,
        crop_shape=[int(r1 - r0), int(c1 - c0)],
        ndvi_min=float(np.nanmin(crop_ndvi)),
        ndvi_mean=float(np.nanmean(crop_ndvi)),
        ndvi_max=float(np.nanmax(crop_ndvi)),
        distance_to_shore_m=float(patch.dist_to_shore_m),
        candidate_pixels=int(crop_mask.sum()),
        message=(
            f"crop={r1-r0}x{c1-c0}px, NDVI min/mean/max="
            f"{np.nanmin(crop_ndvi):.3f}/{np.nanmean(crop_ndvi):.3f}/"
            f"{np.nanmax(crop_ndvi):.3f}, shore distance={patch.dist_to_shore_m:.1f}m."
        ),
    )


def alt_analysis(context: SceneContext, first: AnalyzeEvidence, threshold: float = 0.40) -> AlternativeEvidence:
    """Run a second NDVI-only mask with a chosen threshold and compute IoU."""
    open_water = _open_water(context.reference_lake)
    alternate = open_water & (ndvi_of(context.red, context.nir) > threshold)
    first_mask = first.candidate_mask
    intersection = int(np.logical_and(first_mask, alternate).sum())
    union = int(np.logical_or(first_mask, alternate).sum())
    iou = intersection / union if union else 1.0
    return AlternativeEvidence(
        status=EvidenceStatus.OK,
        threshold=threshold,
        first_pixels=int(first_mask.sum()),
        alternate_pixels=int(alternate.sum()),
        intersection_pixels=intersection,
        union_pixels=union,
        iou=float(iou),
        message=(
            f"NDVI formula=(NIR-red)/(NIR+red); threshold={threshold:.2f}, "
            f"first={first_mask.sum()}px, alternate={alternate.sum()}px, IoU={iou:.3f}."
        ),
    )


def fetch_alternate_scene(context: SceneContext, used_dates: Sequence[str]) -> FetchEvidence:
    remaining = [s for s in context.alternate_scenes if s.date not in used_dates]
    if not remaining:
        return FetchEvidence(
            status=EvidenceStatus.UNAVAILABLE,
            selected_date=None,
            selected_scene_id=None,
            remaining_scene_count=0,
            cloud_fraction=None,
            message="No alternate scene remains in the supplied clear-scene set.",
        )
    selected = min(remaining, key=lambda item: box_cloud(item.scl))
    return FetchEvidence(
        status=EvidenceStatus.OK,
        selected_date=selected.date,
        selected_scene_id=selected.scene_id,
        remaining_scene_count=len(remaining) - 1,
        cloud_fraction=float(box_cloud(selected.scl)),
        message=(
            f"Selected next-best scene {selected.date} ({selected.scene_id}); "
            f"cloud={box_cloud(selected.scl):.4f}, "
            f"{len(remaining)-1} alternate scene(s) remain."
        ),
    )


def request_human_verification(analyze: AnalyzeEvidence) -> HumanEvidence:
    open_water_px = analyze.open_water_pixels
    open_water_ha = getattr(analyze, "open_water_area_ha", round(open_water_px * 0.01, 2))
    patch_ha = getattr(analyze, "patch_area_ha", round(float(analyze.scene.candidate_area_ha), 2))
    patch_px = getattr(analyze, "patch_pixels", int(round(patch_ha / 0.01)))

    if patch_px == 0 and open_water_px == 0:
        return HumanEvidence(
            status=EvidenceStatus.SKIPPED,
            pending=False,
            candidate_pixels=0,
            candidate_area_ha=0.0,
            open_water_pixels=0,
            open_water_area_ha=0.0,
            patch_pixels=0,
            patch_area_ha=0.0,
            message="No candidate pixels exist; human verification is not pending.",
        )
    return HumanEvidence(
        status=EvidenceStatus.PENDING,
        pending=True,
        candidate_pixels=patch_px if patch_px > 0 else open_water_px,
        candidate_area_ha=patch_ha if patch_ha > 0 else open_water_ha,
        open_water_pixels=open_water_px,
        open_water_area_ha=open_water_ha,
        patch_pixels=patch_px,
        patch_area_ha=patch_ha,
        message=(
            f"Human verification pending: total candidate area={patch_ha:.2f} ha ({patch_px} px); "
            f"open-water core={open_water_ha:.2f} ha ({open_water_px} px)."
        ),
    )
