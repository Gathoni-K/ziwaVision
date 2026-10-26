"""Run Active Inspector against real cases already present in the repository."""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from inspector import inspect_hotspot
from pipeline import box_cloud, find_scenes, lake_mask, read_band, read_scl, reference_lake
from tools import SceneContext

BBOX = [34.73, -0.22, 34.83, -0.12]
DATE_RANGE = "2026-07-01/2026-09-30"


def load_contexts() -> Dict[str, SceneContext]:
    scenes = find_scenes(BBOX, DATE_RANGE, max_items=30)
    raw = []
    for scene in sorted(scenes, key=lambda item: item.datetime):
        red = read_band(scene, "red", BBOX)
        scl = read_scl(scene, BBOX, red)
        if box_cloud(scl) > 0.05:
            continue
        lake = lake_mask(scl)
        if lake is not None:
            raw.append((scene, red, scl, lake))
    if not raw:
        raise RuntimeError("No clear scenes with lake masks available.")
    stable = reference_lake([entry[3] for entry in raw], min_share=0.6)
    ref_path = os.path.join(os.path.dirname(_HERE), "outputs", "reference_mask.png")
    reference_mask = cv2.imread(ref_path, cv2.IMREAD_GRAYSCALE)
    contexts: Dict[str, SceneContext] = {}
    for scene, red, scl, lake in raw:
        contexts[str(scene.datetime.date())] = SceneContext(
            scene_id=scene.id,
            date=str(scene.datetime.date()),
            location="Dunga Beach, Winam Gulf",
            bbox=BBOX,
            red=red,
            nir=read_band(scene, "nir", BBOX),
            green=read_band(scene, "green", BBOX),
            blue=read_band(scene, "blue", BBOX),
            scl=scl,
            lake_filled=lake,
            reference_lake=stable,
            reference_mask=reference_mask,
        )
    for context in contexts.values():
        context.alternate_scenes = tuple(
            candidate for candidate in contexts.values() if candidate.date != context.date
        )
    return contexts


def main() -> None:
    contexts = load_contexts()
    with open(os.path.join(os.path.dirname(_HERE), "outputs", "results.json")) as handle:
        results = {row["date"]: row for row in json.load(handle)}
    site_scan_dates: List[str] = []
    scan_path = os.path.join(os.path.dirname(_HERE), "outputs", "site_scan.csv")
    if os.path.exists(scan_path):
        import csv
        with open(scan_path) as handle:
            site_scan_dates = sorted({
                row["date"] for row in csv.DictReader(handle)
                if int(row["candidate_pixels"]) > 0
            })
    requested = ["2026-07-04", "2026-07-06", "2026-08-23"]
    zero = next(
        date for date, result in results.items()
        if result["n_patches"] == 0 and result["cloud_fraction"] <= 0.05
    )
    requested.append(zero)
    requested.extend(date for date in site_scan_dates if date not in requested)
    selected = [date for date in requested if date in contexts]
    print(f"Real cases available: {', '.join(selected)}")
    if not any(date not in contexts for date in requested):
        print("Every requested case type occurred in the supplied real data.")
    all_records = []
    for date in selected:
        context = contexts[date]
        records = inspect_hotspot(context, list(context.alternate_scenes), max_steps=8)
        all_records.extend(records)
        print(f"\nCASE {date}")
        for record in records:
            print(
                f" step {record.step}: {record.decision}; "
                f"{record.outcome} -> next action was selected from those OpenCV numbers"
            )
    expected_actions = {
        "no_candidate",
        "fetch_alternate_scene",
        "inspect_crop",
        "alt_analysis",
        "request_human_verification",
        "reject_mask_artifact",
        "needs_verification",
    }
    observed = {record.decision for record in all_records}
    print("\nACTION COVERAGE")
    for action in sorted(expected_actions):
        state = "occurred" if action in observed else "did not occur in supplied real cases"
        print(f" {action}: {state}")


if __name__ == "__main__":
    main()
