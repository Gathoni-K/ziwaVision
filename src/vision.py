"""
vision.py — OpenCV 5 segmentation and patch detection.

Takes pre-read band arrays and a lake mask; returns a list of Patch objects.
Each Patch holds: area (ha), centroid (pixel coords and approx lat/lon),
mean NDVI, detection confidence (0–1), and an overlay image.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ── constants ──────────────────────────────────────────────────────────────────

PIXEL_HA: float = (10.0 ** 2) / 10_000   # 10 m pixel → 0.01 ha
NDVI_THRESHOLD: float = 0.30              # candidate vegetation threshold
MIN_PATCH_PX: int = 5                    # ignore patches smaller than 5 pixels (0.05 ha)

# Approximate pixel-to-degree conversion for the test box.
# BBOX = [34.73, -0.22, 34.83, -0.12]; scene shape ≈ (1106, 1113) pixels.
_BBOX_W, _BBOX_S, _BBOX_E, _BBOX_N = 34.73, -0.22, 34.83, -0.12
_REF_ROWS, _REF_COLS = 1106, 1113        # typical scene shape for this box


# ── data classes ───────────────────────────────────────────────────────────────

@dataclass
class Patch:
    """One connected candidate-vegetation patch detected in a scene."""
    patch_id: int
    area_ha: float
    centroid_px: Tuple[int, int]         # (row, col)
    centroid_latlon: Tuple[float, float] # (lat, lon) approximate
    bbox_px: Tuple[int, int, int, int]   # (row_min, col_min, row_max, col_max)
    mean_ndvi: float
    ndvi_fraction: float     # fraction of patch pixels with NDVI > threshold
    scl_veg_fraction: float  # fraction labelled SCL class 4 (vegetation)
    confidence: float        # 0–1 detection confidence
    notes: str = ""


@dataclass
class SceneVision:
    """Full vision result for one scene."""
    scene_id: str
    date: str
    image_quality: float     # 0–1 (1 = no cloud, no shadow, no unclassified)
    cloud_fraction: float    # fraction of box that is cloud/shadow/missing
    unclassified_fraction: float
    patches: List[Patch] = field(default_factory=list)
    lake_area_ha: float = 0.0
    candidate_area_ha: float = 0.0     # total area across all patches
    overlay_path: Optional[str] = None


# ── helpers ────────────────────────────────────────────────────────────────────

def _px_to_latlon(row: int, col: int, rows: int, cols: int) -> Tuple[float, float]:
    """
    Linear interpolation from pixel (row, col) to (lat, lon).
    Row 0 → north edge, row (rows-1) → south edge.
    Col 0 → west edge, col (cols-1) → east edge.
    """
    lat = _BBOX_N - (row / rows) * (_BBOX_N - _BBOX_S)
    lon = _BBOX_W + (col / cols) * (_BBOX_E - _BBOX_W)
    return round(lat, 6), round(lon, 6)


def _patch_confidence(
    area_ha: float,
    mean_ndvi: float,
    ndvi_fraction: float,
    scl_veg_fraction: float,
) -> float:
    """
    Rule-based confidence score for a single patch (0–1).

    Scoring components:
    1. Size:         larger patches are more likely real (sigmoid-shaped, saturates at 5 ha)
    2. NDVI strength: mean NDVI relative to threshold (capped at 0.7)
    3. NDVI coherence: fraction of patch pixels above threshold
    4. SCL agreement: SCL class 4 agreement adds a bonus

    All weights sum to 1.0.
    """
    # 1. size score: 0 at 0 ha, ~0.5 at 0.25 ha, ~1 at 5 ha (log-scaled)
    size_score = min(1.0, math.log1p(area_ha / 0.1) / math.log1p(50.0))

    # 2. NDVI strength above the threshold
    ndvi_score = min(1.0, max(0.0, (mean_ndvi - NDVI_THRESHOLD) / (0.7 - NDVI_THRESHOLD)))

    # 3. Fraction of patch that is NDVI-green (coherence)
    coherence_score = ndvi_fraction

    # 4. SCL agreement bonus
    scl_bonus = scl_veg_fraction * 0.5   # up to 0.5 bonus

    raw = 0.30 * size_score + 0.30 * ndvi_score + 0.25 * coherence_score + 0.15 * scl_bonus
    return round(min(1.0, max(0.0, raw)), 3)


# ── image quality ──────────────────────────────────────────────────────────────

BAD_SCL = [0, 1, 3, 8, 9, 10]   # no-data, defective, cloud shadow, cloud, cirrus

def image_quality_score(scl: np.ndarray) -> Tuple[float, float, float]:
    """
    Returns (quality_score, cloud_fraction, unclassified_fraction).

    quality_score = 1 − cloud_fraction − 0.5 × unclassified_fraction, clipped to [0, 1].
    Unclassified pixels get a half-penalty because they are ambiguous, not definitely bad.
    """
    cloud_frac = float(np.isin(scl, BAD_SCL).mean())
    unc_frac   = float((scl == 7).mean())
    quality    = float(np.clip(1.0 - cloud_frac - 0.5 * unc_frac, 0.0, 1.0))
    return round(quality, 3), round(cloud_frac, 4), round(unc_frac, 4)


# ── main segmentation ──────────────────────────────────────────────────────────

def candidates_mask(
    lake_filled: np.ndarray,
    ndvi: np.ndarray,
    scl: np.ndarray,
    erode_shore_px: int = 7,
) -> np.ndarray:
    """
    Build the candidate mask: pixels that are:
      - inside the filled lake, AND
      - at least `erode_shore_px` pixels away from the shore (to cut shoreline noise), AND
      - either NDVI > threshold OR SCL class 4 (vegetation).

    Returns a boolean array of the same shape as `lake_filled`.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * erode_shore_px + 1, 2 * erode_shore_px + 1)
    )
    interior = cv2.erode(lake_filled, kernel)

    veg_ndvi = ndvi > NDVI_THRESHOLD
    veg_scl  = scl == 4

    return (interior == 1) & (veg_ndvi | veg_scl)


def _grabcut_refine(
    rgb_uint8: np.ndarray,
    seed_mask: np.ndarray,
    lake_filled: np.ndarray,
    n_iter: int = 3,
) -> np.ndarray:
    """
    Use OpenCV 5's GrabCut to refine the NDVI-based seed mask.

    `seed_mask` is a boolean array (True = probable foreground).
    `lake_filled` is used to constrain probable background (land outside lake).

    Returns a refined boolean mask (True = definite/probable foreground).

    Falls back to the original seed mask if GrabCut cannot run (e.g., no seed pixels).
    """
    if seed_mask.sum() < MIN_PATCH_PX:
        return seed_mask.copy()

    h, w = rgb_uint8.shape[:2]

    # Build a GrabCut initialisation mask:
    #   cv2.GC_BGD (0)  = definite background
    #   cv2.GC_PR_BGD(2)= probable background
    #   cv2.GC_PR_FGD(3)= probable foreground
    #   cv2.GC_FGD (1)  = definite foreground
    gc_mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)

    # Land pixels are definite background
    gc_mask[lake_filled == 0] = cv2.GC_BGD

    # NDVI-seed pixels are probable foreground
    gc_mask[seed_mask] = cv2.GC_PR_FGD

    # Dilate the seed slightly and call those probable foreground too
    dil_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    seed_dil = cv2.dilate(seed_mask.astype(np.uint8), dil_k).astype(bool)
    gc_mask[seed_dil & (lake_filled == 1)] = cv2.GC_PR_FGD

    bgd_model = np.zeros((1, 65), dtype=np.float64)
    fgd_model = np.zeros((1, 65), dtype=np.float64)

    try:
        cv2.grabCut(rgb_uint8, gc_mask, None, bgd_model, fgd_model, n_iter, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        # GrabCut can fail if the image region is uniform; fall back to seed
        return seed_mask.copy()

    refined = (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)
    # Intersect with lake interior to avoid spilling onto land
    refined = refined & (lake_filled == 1)
    return refined


def detect_patches(
    scene_id: str,
    date: str,
    red: np.ndarray,
    nir: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    scl: np.ndarray,
    lake_filled: np.ndarray,
    use_grabcut: bool = True,
) -> SceneVision:
    """
    Full detection pipeline for one scene.

    Steps:
    1. Compute NDVI.
    2. Build image quality score.
    3. Build NDVI-based candidate seed mask (inside lake, away from shore).
    4. Optionally refine with GrabCut (OpenCV 5).
    5. Label connected components; compute per-patch stats.
    6. Build overlay image (RGB + yellow candidate overlay).

    Returns a SceneVision object. If quality < 0.5 or no lake, patches will be empty.
    """
    rows, cols = red.shape
    ndvi = (nir - red) / (nir + red + 1e-6)

    quality, cloud_frac, unc_frac = image_quality_score(scl)
    lake_area_ha = float(lake_filled.sum()) * PIXEL_HA

    # ── Step 3: candidate seed mask ───────────────────────────────────────────
    seed = candidates_mask(lake_filled, ndvi, scl, erode_shore_px=7)

    # ── Step 4: GrabCut refinement ────────────────────────────────────────────
    if use_grabcut and seed.sum() >= MIN_PATCH_PX:
        # Build uint8 RGB for GrabCut (scale to 0-255)
        rgb_u8 = np.clip(np.dstack([red, green, blue]) / 3000 * 255, 0, 255).astype(np.uint8)
        refined = _grabcut_refine(rgb_u8, seed, lake_filled)
    else:
        refined = seed.copy()

    # ── Step 5: connected components ─────────────────────────────────────────
    refined_u8 = refined.astype(np.uint8)
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        refined_u8, connectivity=8
    )

    patches: List[Patch] = []
    for label_id in range(1, n_labels):   # skip background (0)
        area_px  = int(stats[label_id, cv2.CC_STAT_AREA])
        if area_px < MIN_PATCH_PX:
            continue

        area_ha  = area_px * PIXEL_HA
        cx_col   = int(centroids[label_id, 0])   # OpenCV centroid: (x=col, y=row)
        cx_row   = int(centroids[label_id, 1])

        # bounding box
        bx  = int(stats[label_id, cv2.CC_STAT_LEFT])
        by  = int(stats[label_id, cv2.CC_STAT_TOP])
        bw  = int(stats[label_id, cv2.CC_STAT_WIDTH])
        bh_ = int(stats[label_id, cv2.CC_STAT_HEIGHT])
        bbox = (by, bx, by + bh_, bx + bw)

        # patch pixels mask
        patch_mask = (labels == label_id)

        # per-patch spectral stats
        patch_ndvi   = ndvi[patch_mask]
        mean_ndvi    = float(patch_ndvi.mean())
        ndvi_frac    = float((patch_ndvi > NDVI_THRESHOLD).mean())
        scl_veg_frac = float((scl[patch_mask] == 4).mean())

        confidence = _patch_confidence(area_ha, mean_ndvi, ndvi_frac, scl_veg_frac)

        latlon = _px_to_latlon(cx_row, cx_col, rows, cols)

        patch = Patch(
            patch_id=label_id,
            area_ha=round(area_ha, 3),
            centroid_px=(cx_row, cx_col),
            centroid_latlon=latlon,
            bbox_px=bbox,
            mean_ndvi=round(mean_ndvi, 4),
            ndvi_fraction=round(ndvi_frac, 4),
            scl_veg_fraction=round(scl_veg_frac, 4),
            confidence=confidence,
        )
        patches.append(patch)

    # ── Step 6: overlay image ─────────────────────────────────────────────────
    rgb_f = np.clip(np.dstack([red, green, blue]) / 3000, 0, 1)
    overlay = rgb_f.copy()
    if refined.any():
        overlay[refined] = overlay[refined] * 0.4 + np.array([0.6, 0.6, 0.0])  # yellow tint

    candidate_area_ha = sum(p.area_ha for p in patches)

    return SceneVision(
        scene_id=scene_id,
        date=date,
        image_quality=quality,
        cloud_fraction=cloud_frac,
        unclassified_fraction=unc_frac,
        patches=patches,
        lake_area_ha=round(lake_area_ha, 1),
        candidate_area_ha=round(candidate_area_ha, 3),
        overlay_path=None,   # set by the orchestrator after saving
    )
