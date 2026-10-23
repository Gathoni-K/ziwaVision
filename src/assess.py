"""
assess.py — Image quality + detection confidence scorer.

Wraps the outputs of vision.py and reference.py into a single
SceneAssessment dataclass that the agent consumes.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from vision import SceneVision
from reference import compare_to_reference, reference_match_summary, mean_reference_iou
import numpy as np


# ── data class ─────────────────────────────────────────────────────────────────

@dataclass
class SceneAssessment:
    """
    Full quality and confidence assessment for one scene.
    This is the object the agent reads to make its decision.
    """
    # ── scene identity ─────────────────────────────────────────────────────────
    scene_id: str
    date: str

    # ── image quality (from vision.image_quality_score) ────────────────────────
    image_quality: float       # 0–1  (1 = perfectly clear)
    cloud_fraction: float      # fraction of box that is cloud / shadow / missing
    unclassified_fraction: float

    # ── detection results ──────────────────────────────────────────────────────
    n_patches: int
    total_area_ha: float
    mean_patch_confidence: float   # area-weighted mean of per-patch confidence
    lake_area_ha: float

    # ── reference comparison ───────────────────────────────────────────────────
    scene_iou: float               # overall IoU vs reference mask
    mean_patch_iou: float          # mean per-patch IoU
    n_in_reference: int            # patches that overlap reference ≥ 10%

    # ── patch-level detail (for JSON serialisation) ────────────────────────────
    patch_details: List[Dict]

    # ── overlay image path ─────────────────────────────────────────────────────
    overlay_path: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


# ── builder ────────────────────────────────────────────────────────────────────

def assess(
    scene_vision: SceneVision,
    reference_mask: Optional[np.ndarray],
) -> SceneAssessment:
    """
    Combine a SceneVision result with a reference mask comparison.

    `reference_mask` may be None if the reference hasn't been built yet
    (e.g., when processing the reference scene itself); in that case all
    reference scores are 0.
    """
    sv = scene_vision

    # ── Area-weighted mean confidence across patches ─────────────────────────
    if sv.patches:
        total_ha = sum(p.area_ha for p in sv.patches)
        if total_ha > 0:
            weighted_conf = sum(p.confidence * p.area_ha for p in sv.patches) / total_ha
        else:
            weighted_conf = sum(p.confidence for p in sv.patches) / len(sv.patches)
    else:
        total_ha = 0.0
        weighted_conf = 0.0

    # ── Reference comparison ─────────────────────────────────────────────────
    if reference_mask is not None and sv.patches:
        # Build a detected mask from all patches (any NDVI candidate pixel)
        # We need the per-patch component labels — build from the patch list
        # by creating a mask that is True wherever any patch pixel was detected.
        # The vision module already has the refined mask; we reconstruct it from
        # patch bounding boxes + the fact that all returned patches passed the
        # size filter.
        # For simplicity, we create a mask of the union of all patch bounding
        # boxes and use scene_iou at the scene level (compare all candidates).
        # A per-patch comparison against reference is computed separately.
        import numpy as np
        h, w = reference_mask.shape
        detected_mask = np.zeros((h, w), dtype=np.uint8)
        for p in sv.patches:
            r0, c0, r1, c1 = p.bbox_px
            # Paint the bounding-box region as detected (conservative approximation)
            detected_mask[r0:r1, c0:c1] = 1

        scene_iou, patch_matches = compare_to_reference(detected_mask, reference_mask)
        ref_summary = reference_match_summary(scene_iou, patch_matches)
    else:
        scene_iou = 0.0
        patch_matches = []
        ref_summary = reference_match_summary(0.0, [])

    # ── Patch detail dicts ───────────────────────────────────────────────────
    patch_details = []
    for p in sv.patches:
        pd = {
            "patch_id":        p.patch_id,
            "area_ha":         p.area_ha,
            "centroid_latlon": list(p.centroid_latlon),
            "centroid_px":     list(p.centroid_px),
            "mean_ndvi":       p.mean_ndvi,
            "ndvi_fraction":   p.ndvi_fraction,
            "scl_veg_fraction": p.scl_veg_fraction,
            "confidence":      p.confidence,
        }
        # Attach per-patch IoU if available
        if patch_matches:
            match = next((m for m in patch_matches if m.patch_id == p.patch_id), None)
            pd["reference_iou"] = match.iou if match else 0.0
            pd["in_reference"]  = match.in_reference if match else False
        patch_details.append(pd)

    return SceneAssessment(
        scene_id=sv.scene_id,
        date=sv.date,
        image_quality=sv.image_quality,
        cloud_fraction=sv.cloud_fraction,
        unclassified_fraction=sv.unclassified_fraction,
        n_patches=len(sv.patches),
        total_area_ha=round(total_ha, 3),
        mean_patch_confidence=round(weighted_conf, 3),
        lake_area_ha=sv.lake_area_ha,
        scene_iou=ref_summary["scene_iou"],
        mean_patch_iou=ref_summary["mean_patch_iou"],
        n_in_reference=ref_summary["n_in_reference"],
        patch_details=patch_details,
        overlay_path=sv.overlay_path,
    )
