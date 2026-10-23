"""
reference.py — Compare detected patches against labelled reference imagery.

The reference is built once from the clearest scene (2026-08-28, 0% cloud,
100% lake coverage). Its candidate patches become the reference labels —
no manual annotation is needed for the MVP.

The checker computes per-patch IoU (intersection over union) against the
reference mask. A patch that overlaps well with reference vegetation gets
a high reference_match score.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

PIXEL_HA: float = (10.0 ** 2) / 10_000

# ── data class ─────────────────────────────────────────────────────────────────

@dataclass
class PatchMatch:
    """IoU result for one detected patch against the reference mask."""
    patch_id: int
    iou: float            # intersection-over-union, 0–1
    in_reference: bool    # True if IoU >= 0.10 (patch overlaps reference at all)


# ── build reference mask from the reference-date patches ──────────────────────

def build_reference_mask(
    candidate_mask: np.ndarray,
    save_path: Optional[str] = None,
) -> np.ndarray:
    """
    Convert a boolean candidate mask from the reference date into a binary
    reference mask (uint8, 0/1).  Optionally saves a PNG for inspection.

    `candidate_mask` is the output of vision.candidates_mask() on the
    clearest scene (e.g. 2026-08-28).
    """
    ref = candidate_mask.astype(np.uint8)
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, ref * 255)
    return ref


def save_reference_labels(
    patches: list,          # list of vision.Patch objects
    shape: Tuple[int, int],
    path: str,
) -> None:
    """
    Serialize the reference patches to JSON for the API and dashboard.
    `patches` is the list of Patch objects from the reference scene.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = [
        {
            "patch_id":      p.patch_id,
            "area_ha":       p.area_ha,
            "centroid_px":   list(p.centroid_px),
            "centroid_latlon": list(p.centroid_latlon),
            "mean_ndvi":     p.mean_ndvi,
            "confidence":    p.confidence,
        }
        for p in patches
    ]
    with open(path, "w") as f:
        json.dump({"shape": list(shape), "patches": data}, f, indent=2)


# ── per-scene comparison ───────────────────────────────────────────────────────

def compare_to_reference(
    detected_mask: np.ndarray,
    reference_mask: np.ndarray,
) -> Tuple[float, List[PatchMatch]]:
    """
    Compare a detected candidate mask to the reference mask.

    Returns:
        (scene_iou, []):
        - scene_iou: overall IoU for all detected candidates vs reference.
        - patch_matches: per-connected-component IoU list.

    Both masks must be the same shape (rows, cols), dtype uint8 or bool.
    """
    det = detected_mask.astype(bool)
    ref = reference_mask.astype(bool)

    # ── Overall scene-level IoU ───────────────────────────────────────────────
    intersection = (det & ref).sum()
    union        = (det | ref).sum()
    scene_iou    = float(intersection / union) if union > 0 else 0.0

    # ── Per-patch IoU (over connected components of detected mask) ────────────
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        det.astype(np.uint8), connectivity=8
    )
    patch_matches: List[PatchMatch] = []
    for label_id in range(1, n_labels):
        patch_pixels = (labels == label_id)
        p_inter = (patch_pixels & ref).sum()
        p_union = (patch_pixels | ref).sum()
        iou = float(p_inter / p_union) if p_union > 0 else 0.0
        patch_matches.append(PatchMatch(
            patch_id=label_id,
            iou=round(iou, 4),
            in_reference=(iou >= 0.10),
        ))

    return round(scene_iou, 4), patch_matches


def mean_reference_iou(patch_matches: List[PatchMatch]) -> float:
    """Average IoU across all detected patches (0.0 if no patches)."""
    if not patch_matches:
        return 0.0
    return round(sum(m.iou for m in patch_matches) / len(patch_matches), 4)


def reference_match_summary(
    scene_iou: float,
    patch_matches: List[PatchMatch],
) -> Dict:
    """Build a summary dict for JSON serialisation."""
    return {
        "scene_iou":        scene_iou,
        "mean_patch_iou":   mean_reference_iou(patch_matches),
        "n_patches_checked": len(patch_matches),
        "n_in_reference":   sum(1 for m in patch_matches if m.in_reference),
        "patches":          [
            {"patch_id": m.patch_id, "iou": m.iou, "in_reference": m.in_reference}
            for m in patch_matches
        ],
    }
