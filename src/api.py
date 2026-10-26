"""
api.py — Lightweight Flask REST API for ZiwaVision.

Endpoints:
    GET  /api/hotspots              → returns all entries from results.json
    GET  /api/hotspots/<date>       → returns one entry by date
    POST /api/verify                → body {date, patch_id?, verified: bool}
                                       updates verification_status in results.json
    GET  /api/overlay/<date>        → serves overlay PNG for that date
    GET  /health                    → liveness check

Usage (local):
    python src/api.py               (runs on http://localhost:5050)

For AWS Lambda, this file is wrapped by Mangum:
    handler = Mangum(app)           (uncomment the import at the bottom)

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import json
import os
import sys

from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS

# ── path setup (allow running from project root or src/) ───────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agent import apply_verification

# ── config ─────────────────────────────────────────────────────────────────────
OUTPUTS_DIR   = os.path.join(_ROOT, "outputs")
RESULTS_PATH  = os.path.join(OUTPUTS_DIR, "results.json")
OVERLAYS_DIR  = os.path.join(OUTPUTS_DIR, "overlays")
PORT          = int(os.environ.get("PORT", 5050))

# S3 config — set by the SAM template via environment variables.
# When RESULTS_BUCKET is absent the API falls back to the local file.
# boto3 is imported lazily so local development does not require AWS creds.
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")  # e.g. "ziwavision-dashboard"
S3_RESULTS_KEY = "data/results.json"  # must match the path synced by deploy.sh

app = Flask(__name__)
CORS(app)   # allow the dashboard to call from any origin


# ── helpers ────────────────────────────────────────────────────────────────────

def _s3_client():
    """Return a boto3 S3 client. Imported lazily to keep local dev clean."""
    import boto3  # noqa: PLC0415
    return boto3.client("s3")


def _load_results() -> list:
    """
    Return the results list.

    On Lambda (RESULTS_BUCKET is set): fetch results.json from S3.
    Locally: read from the outputs/ directory on disk.
    """
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            obj = s3.get_object(Bucket=RESULTS_BUCKET, Key=S3_RESULTS_KEY)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"S3 _load_results failed ({exc}); falling back to local file")
    # Local fallback
    if not os.path.exists(RESULTS_PATH):
        return []
    with open(RESULTS_PATH) as f:
        return json.load(f)


def _save_results(results: list) -> None:
    """
    Persist the results list.

    On Lambda (RESULTS_BUCKET is set): PUT results.json to S3.
    Locally: write to the outputs/ directory on disk.
    """
    payload = json.dumps(results, indent=2)
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=S3_RESULTS_KEY,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            return
        except Exception as exc:  # noqa: BLE001
            print(f"S3 _save_results failed ({exc}); falling back to local file")
    # Local fallback
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        f.write(payload)


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ZiwaVision API"})


@app.get("/api/hotspots")
def get_hotspots():
    """Return all scene results, sorted by date descending."""
    results = _load_results()
    results.sort(key=lambda r: r.get("date", ""), reverse=True)
    return jsonify(results)


@app.get("/api/hotspots/<date>")
def get_hotspot(date: str):
    """Return the result for a single date (YYYY-MM-DD)."""
    results = _load_results()
    entry = next((r for r in results if r.get("date") == date), None)
    if entry is None:
        abort(404, description=f"No result found for date {date!r}")
    return jsonify(entry)


@app.post("/api/verify")
def verify():
    """
    Human verification endpoint.
    Body (JSON): { "date": "YYYY-MM-DD", "patch_id": <int|null>, "verified": true|false }

    Updates verification_status to "verified" or "uncertain".
    Returns the updated entry.
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Request body must be JSON")

    date     = body.get("date")
    verified = body.get("verified")
    patch_id = body.get("patch_id")   # optional
    status   = body.get("status")     # optional: "verified" | "uncertain" | "rejected"

    if date is None:
        abort(400, description="'date' is required")
    if verified is None and status is None:
        abort(400, description="Either 'verified' or 'status' is required")

    results = _load_results()
    results = apply_verification(results, date, patch_id, bool(verified), status=status)
    _save_results(results)

    updated = next((r for r in results if r.get("date") == date), None)
    return jsonify({"ok": True, "updated": updated})


@app.get("/api/overlay/<date>")
def get_overlay(date: str):
    """Serve the overlay PNG for the given date."""
    safe_date = date.replace("..", "").replace("/", "")   # very basic sanitisation
    path = os.path.join(OVERLAYS_DIR, f"{safe_date}.png")
    if not os.path.exists(path):
        abort(404, description=f"No overlay image for date {date!r}")
    return send_file(path, mimetype="image/png")


@app.get("/api/reference")
def get_reference():
    """Return the reference patch labels."""
    ref_path = os.path.join(OUTPUTS_DIR, "reference_labels.json")
    if not os.path.exists(ref_path):
        return jsonify({"patches": [], "note": "reference not yet built"})
    with open(ref_path) as f:
        return jsonify(json.load(f))


# ── Lambda handler (uncomment for AWS deploy) ──────────────────────────────────
# from mangum import Mangum
# handler = Mangum(app)


# ── local dev server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(RESULTS_PATH):
        print(f"WARNING: {RESULTS_PATH} not found.")
        print("Run 'python src/run_pipeline.py' first to generate results.")
    print(f"Starting ZiwaVision API on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
