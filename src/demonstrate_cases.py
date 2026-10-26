"""
demonstrate_cases.py — End-to-end live demonstration of the three required cases:
1. Successful live-data inspection with candidate vegetation (e.g., 2026-08-23).
2. Zero-candidate outcome on a clear date (e.g., 2026-08-28).
3. Explicit failure case (e.g., date with no Sentinel-2 coverage or asset access fault).
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from inspector import run_live_inspection
from trace import load_traces

BBOX = [34.73, -0.22, 34.83, -0.12]


def demonstrate():
    print("=" * 70)
    print("ZIWAVISION ACTIVE INSPECTOR — LIVE DATA DEMONSTRATION")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────────
    # CASE 1: Successful live-data inspection with candidate vegetation
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("CASE 1: Live-Data Inspection with Candidate Vegetation (2026-08-23)")
    print("Connecting to live Element84 Earth Search → S2 COG assets → OpenCV 5...")
    print("─" * 70)
    res_success = run_live_inspection("2026-08-23", bbox=BBOX)
    print(f"Status OK: {res_success.get('ok')}")
    print(f"Decision: {res_success.get('decision')}")
    print(f"Verification Status: {res_success.get('status')}")
    if res_success.get("hotspot"):
        h = res_success["hotspot"]
        print(f"Scene ID: {h['scene_id']}")
        print(f"Quality: {h['image_quality']} | Cloud: {h['cloud_fraction']}")
        print(f"Detected Patches: {h['n_patches']} | Total Area: {h['total_area_ha']} ha")
        print(f"Agent Reason: {h['agent_reason']}")
        print(f"Overlay Path: {h['overlay_path']}")
    print(f"Persisted Traces ({len(res_success.get('traces', []))} steps):")
    for t in res_success.get("traces", []):
        print(f"  Step {t['step']}: {t['decision']} → {t['outcome']}")

    # ─────────────────────────────────────────────────────────────────────────────
    # CASE 2: Zero-candidate outcome
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("CASE 2: Zero-Candidate Outcome on Clear Date (2026-08-28)")
    print("Connecting to live Element84 Earth Search → S2 COG assets → OpenCV 5...")
    print("─" * 70)
    res_zero = run_live_inspection("2026-08-28", bbox=BBOX)
    print(f"Status OK: {res_zero.get('ok')}")
    print(f"Decision: {res_zero.get('decision')}")
    print(f"Verification Status: {res_zero.get('status')}")
    if res_zero.get("hotspot"):
        h = res_zero["hotspot"]
        print(f"Scene ID: {h['scene_id']}")
        print(f"Quality: {h['image_quality']} | Cloud: {h['cloud_fraction']}")
        print(f"Detected Patches: {h['n_patches']} | Total Area: {h['total_area_ha']} ha")
        print(f"Agent Reason: {h['agent_reason']}")
    print(f"Persisted Traces ({len(res_zero.get('traces', []))} steps):")
    for t in res_zero.get("traces", []):
        print(f"  Step {t['step']}: {t['decision']} → {t['outcome']}")

    # ─────────────────────────────────────────────────────────────────────────────
    # CASE 3: Explicit failure case (no silent demo fallback)
    # ─────────────────────────────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("CASE 3: Explicit Failure Case (2026-08-29 — No scene coverage)")
    print("Connecting to live Element84 Earth Search STAC...")
    print("─" * 70)
    res_fail = run_live_inspection("2026-08-29", bbox=BBOX)
    print(f"Status OK: {res_fail.get('ok')} (expected False)")
    print(f"Failure State: {res_fail.get('status')}")
    print(f"Explicit Error: {res_fail.get('error')}")
    print(f"Persisted Failure Traces ({len(res_fail.get('traces', []))} steps):")
    for t in res_fail.get("traces", []):
        print(f"  Step {t['step']}: {t['decision']} → {t['outcome']}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate()
