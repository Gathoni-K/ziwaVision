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

app = Flask(__name__)
CORS(app)   # allow the dashboard to call from any origin


# ── helpers ────────────────────────────────────────────────────────────────────

def _load_results() -> list:
    if not os.path.exists(RESULTS_PATH):
        return []
    with open(RESULTS_PATH) as f:
        return json.load(f)


def _save_results(results: list) -> None:
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


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

    if date is None or verified is None:
        abort(400, description="'date' and 'verified' are required")

    results = _load_results()
    results = apply_verification(results, date, patch_id, bool(verified))
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
