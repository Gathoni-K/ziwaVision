"""
run_pipeline.py — Orchestration: loop all dates, run vision → assess → agent.

Usage (from project root, venv activated):
    python src/run_pipeline.py

Outputs:
    outputs/results.json            — all scene assessments + agent decisions
    outputs/decisions.jsonl         — append-only agent decision log
    outputs/reference_labels.json   — reference patches from the clearest scene
    outputs/overlays/<date>.png     — RGB + candidate overlay per scene
    outputs/reference_mask.png      — the reference candidate mask (B&W)

The reference scene is 2026-08-28 (0% cloud, 100% reference lake coverage).
If that scene is not available the script picks the clearest scene found.

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

# Allow running as `python src/run_pipeline.py` from the project root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pipeline import (
    find_scenes, read_band, read_scl, box_cloud, lake_mask,
    reference_lake, ndvi_of, PIXEL_HA,
)
from vision import detect_patches, candidates_mask
from reference import (
    build_reference_mask, save_reference_labels,
    compare_to_reference, reference_match_summary,
)
from assess import assess
from agent import decide, log_decision

# ── configuration ──────────────────────────────────────────────────────────────

BBOX           = [34.73, -0.22, 34.83, -0.12]
DATE_RANGE     = "2026-07-01/2026-09-30"
REFERENCE_DATE = "2026-08-28"     # clearest scene: 0% cloud, 100% lake coverage
CLOUD_CUTOFF   = 0.05             # box-level cloud fraction threshold

OUTPUTS_DIR    = os.path.join(os.path.dirname(_HERE), "outputs")
OVERLAYS_DIR   = os.path.join(OUTPUTS_DIR, "overlays")
RESULTS_PATH   = os.path.join(OUTPUTS_DIR, "results.json")
DECISIONS_PATH = os.path.join(OUTPUTS_DIR, "decisions.jsonl")
REF_LABELS_PATH = os.path.join(OUTPUTS_DIR, "reference_labels.json")
REF_MASK_PATH  = os.path.join(OUTPUTS_DIR, "reference_mask.png")


# ── helpers ────────────────────────────────────────────────────────────────────

def save_overlay(overlay_rgb: np.ndarray, date: str) -> str:
    """Save the overlay image and return its path."""
    os.makedirs(OVERLAYS_DIR, exist_ok=True)
    path = os.path.join(OVERLAYS_DIR, f"{date}.png")
    plt.imsave(path, np.clip(overlay_rgb, 0, 1))
    return path


def read_scene_bands(scene, bbox):
    """Read all needed bands for one scene. Returns (red, nir, green, blue, scl) or None."""
    try:
        red   = read_band(scene, "red",   bbox)
        nir   = read_band(scene, "nir",   bbox)
        green = read_band(scene, "green", bbox)
        blue  = read_band(scene, "blue",  bbox)
        scl   = read_scl(scene, bbox, red)
        return red, nir, green, blue, scl
    except Exception as exc:
        print(f"  ⚠  band read failed: {exc}")
        return None


def build_overlay(red, green, blue, refined_mask) -> np.ndarray:
    """Build a float RGB overlay with yellow tint over candidate pixels."""
    rgb = np.clip(np.dstack([red, green, blue]) / 3000, 0, 1)
    overlay = rgb.copy()
    if refined_mask is not None and refined_mask.any():
        overlay[refined_mask] = overlay[refined_mask] * 0.4 + np.array([0.6, 0.6, 0.0])
    return overlay


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    os.makedirs(OVERLAYS_DIR, exist_ok=True)

    print("=" * 60)
    print("ZiwaVision — Visual Hotspot Verification Pipeline")
    print("=" * 60)

    # ── 1. Fetch all scenes ───────────────────────────────────────────────────
    print(f"\n[1] Searching Sentinel-2 scenes for {DATE_RANGE} …")
    scenes = find_scenes(BBOX, DATE_RANGE, max_items=30)
    print(f"    {len(scenes)} scene(s) cover the box.")

    if not scenes:
        print("ERROR: no scenes found. Check network and date range.")
        return

    # Index by date
    scene_by_date = {str(s.datetime.date()): s for s in scenes}

    # ── 2. Build multi-date reference lake mask ───────────────────────────────
    print("\n[2] Building reference lake mask …")
    lake_masks = []
    clear_dates = []

    for s in sorted(scenes, key=lambda x: x.datetime.date()):
        bands = read_scene_bands(s, BBOX)
        if bands is None:
            continue
        red, nir, green, blue, scl = bands

        cloud = box_cloud(scl)
        if cloud > CLOUD_CUTOFF:
            print(f"    {s.datetime.date()} skip (cloud {cloud:.1%})")
            continue

        lm = lake_mask(scl)
        if lm is None:
            print(f"    {s.datetime.date()} skip (no lake found)")
            continue

        lake_masks.append(lm)
        clear_dates.append(str(s.datetime.date()))

    if not lake_masks:
        print("ERROR: no clear scenes with a lake mask. Cannot proceed.")
        return

    ref_lake = reference_lake(lake_masks, min_share=0.6)
    print(f"    Reference lake: {ref_lake.sum() * PIXEL_HA:.0f} ha "
          f"from {len(lake_masks)} clear scene(s).")

    # ── 3. Build reference vegetation mask from the reference date ────────────
    print(f"\n[3] Building reference vegetation mask from {REFERENCE_DATE} …")
    ref_date_to_use = REFERENCE_DATE if REFERENCE_DATE in scene_by_date else clear_dates[0]
    if ref_date_to_use != REFERENCE_DATE:
        print(f"    {REFERENCE_DATE} not in scene list; using {ref_date_to_use} instead.")

    ref_scene  = scene_by_date[ref_date_to_use]
    ref_bands  = read_scene_bands(ref_scene, BBOX)
    reference_mask = None
    reference_patches = []

    if ref_bands is not None:
        r_red, r_nir, r_green, r_blue, r_scl = ref_bands
        r_ndvi  = ndvi_of(r_red, r_nir)
        r_lake  = lake_mask(r_scl)
        if r_lake is None:
            r_lake = ref_lake
        r_cands = candidates_mask(r_lake, r_ndvi, r_scl, erode_shore_px=7)

        reference_mask = build_reference_mask(r_cands, save_path=REF_MASK_PATH)

        # Run full detection on the reference scene to get reference patch list
        sv_ref = detect_patches(
            scene_id=ref_scene.id,
            date=ref_date_to_use,
            red=r_red, nir=r_nir, green=r_green, blue=r_blue,
            scl=r_scl, lake_filled=r_lake,
            use_grabcut=True,
        )
        reference_patches = sv_ref.patches
        save_reference_labels(reference_patches, ref_lake.shape, REF_LABELS_PATH)
        print(f"    Reference: {len(reference_patches)} patch(es), "
              f"{sum(p.area_ha for p in reference_patches):.2f} ha total.")
    else:
        print("    WARNING: reference date bands unavailable; IoU comparison disabled.")

    # ── 4. Main loop: process each clear scene ────────────────────────────────
    print(f"\n[4] Processing {len(clear_dates)} clear scene(s) …\n")

    results = []
    # Remove decisions log so we start fresh each run
    if os.path.exists(DECISIONS_PATH):
        os.remove(DECISIONS_PATH)

    for date in sorted(clear_dates):
        scene = scene_by_date[date]
        print(f"  → {date}  {scene.id[:20]}")

        bands = read_scene_bands(scene, BBOX)
        if bands is None:
            continue

        red, nir, green, blue, scl = bands

        # Use the multi-date reference lake if available, else per-scene lake
        lm = lake_mask(scl)
        if lm is None:
            lm = ref_lake

        # ── vision ────────────────────────────────────────────────────────────
        sv = detect_patches(
            scene_id=scene.id,
            date=date,
            red=red, nir=nir, green=green, blue=blue,
            scl=scl, lake_filled=lm,
            use_grabcut=True,
        )

        # ── save overlay ──────────────────────────────────────────────────────
        # Reconstruct overlay from bands (sv has the refined mask embedded in
        # the detection process; we rebuild for display)
        import numpy as _np
        candidate_pixels = _np.zeros(red.shape, dtype=bool)
        for p in sv.patches:
            r0, c0, r1, c1 = p.bbox_px
            candidate_pixels[r0:r1, c0:c1] = True

        overlay_img = build_overlay(red, green, blue, candidate_pixels if sv.patches else None)
        overlay_path = save_overlay(overlay_img, date)
        sv.overlay_path = overlay_path

        # ── assess ────────────────────────────────────────────────────────────
        assessment = assess(sv, reference_mask)
        assessment.overlay_path = overlay_path

        # ── agent decision ────────────────────────────────────────────────────
        decision = decide(assessment)
        log_decision(decision, DECISIONS_PATH)

        # ── print summary ─────────────────────────────────────────────────────
        print(f"     quality={assessment.image_quality:.2f}  "
              f"patches={assessment.n_patches}  "
              f"area={assessment.total_area_ha:.2f} ha  "
              f"conf={assessment.mean_patch_confidence:.2f}  "
              f"IoU={assessment.scene_iou:.3f}  "
              f"→ {decision.action}")

        # ── build result entry ────────────────────────────────────────────────
        entry = {
            "scene_id":   assessment.scene_id,
            "date":       assessment.date,
            "location":   "Dunga Beach, Winam Gulf",
            "bbox":       BBOX,
            "image_quality":          assessment.image_quality,
            "cloud_fraction":         assessment.cloud_fraction,
            "unclassified_fraction":  assessment.unclassified_fraction,
            "n_patches":              assessment.n_patches,
            "total_area_ha":          assessment.total_area_ha,
            "lake_area_ha":           assessment.lake_area_ha,
            "mean_patch_confidence":  assessment.mean_patch_confidence,
            "scene_iou":              assessment.scene_iou,
            "mean_patch_iou":         assessment.mean_patch_iou,
            "n_in_reference":         assessment.n_in_reference,
            "action":                 decision.action,
            "agent_reason":           decision.reason,
            "verification_status":    decision.verification_status,
            "decided_at":             decision.decided_at,
            "overlay_path":           overlay_path,
            "overlay_filename":       os.path.basename(overlay_path),
            "patch_details":          assessment.patch_details,
        }
        results.append(entry)

    # ── 5. Save results.json ──────────────────────────────────────────────────
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    # ── 6. Summary table ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'Date':<12} {'Patches':>7} {'Area ha':>8} {'Conf':>6} {'Action':<35} {'Status'}")
    print("-" * 90)
    for r in sorted(results, key=lambda x: x["date"]):
        print(
            f"{r['date']:<12}"
            f"{r['n_patches']:>7}"
            f"{r['total_area_ha']:>8.2f}"
            f"{r['mean_patch_confidence']:>6.2f}"
            f"  {r['action']:<35}"
            f"  {r['verification_status']}"
        )

    needs_review = [r for r in results if r["verification_status"] == "needs_review"]
    print(f"\n✓ {len(results)} scene(s) processed.")
    print(f"  {len(needs_review)} scene(s) flagged for human verification.")
    print(f"\nOutputs written to:  {OUTPUTS_DIR}/")
    print(f"  results.json        {RESULTS_PATH}")
    print(f"  decisions.jsonl     {DECISIONS_PATH}")
    print(f"  reference_labels    {REF_LABELS_PATH}")
    print(f"  overlays/           {OVERLAYS_DIR}/")
    print("\nNext: start the API with  python src/api.py")


if __name__ == "__main__":
    main()
