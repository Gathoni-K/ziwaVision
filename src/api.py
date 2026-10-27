"""
api.py — Lightweight Flask REST API for ZiwaVision.

Routes
──────
GET  /health                              → liveness check
GET  /api/hotspots                        → all entries from results.json (sorted by date desc)
GET  /api/hotspots/by-date/<date>         → single entry by acquisition date (YYYY-MM-DD)
GET  /api/hotspots/<hotspot_id>           → single entry by stable hotspot ID + attached traces
POST /api/hotspots/<hotspot_id>/verify    → authenticated human-review decision only
POST /api/verify                          → legacy alias kept for dashboard backward compat
POST /api/inspect[/<date>]               → live Earth Search → satellite → OpenCV pipeline
GET  /api/traces/<date>                   → persisted JSONL audit trace for a date
GET  /api/overlay/<date>                  → overlay PNG for that date
GET  /api/reference                       → reference patch labels

Human-review status contract
──────────────────────────────
  Autonomous agent may only set: candidate | needs_verification | uncertain | rejected_as_artefact
  Human reviewer may only set:   verified | rejected
  Any attempt to assign verified/rejected through an unauthenticated path is rejected 403.

Security notes
──────────────
  • ZIWAVISION_API_KEY must be set explicitly in the environment.
  • If unset, the API starts but all verification requests return 503 (not configured).
  • The key is never echoed in logs, traces, or error responses.
  • Bearer token comparison is constant-time (hmac.compare_digest).

Language rule: never say "hyacinth" — always "candidate floating vegetation".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import uuid
from typing import Optional

from flask import Flask, abort, jsonify, request, send_file
from flask_cors import CORS

# ── path setup ─────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agent import apply_verification
from inspector import run_live_inspection
from trace import TraceRecord, append_trace, load_traces

# ── config ─────────────────────────────────────────────────────────────────────
OUTPUTS_DIR   = os.path.join(_ROOT, "outputs")
RESULTS_PATH  = os.path.join(OUTPUTS_DIR, "results.json")
OVERLAYS_DIR  = os.path.join(OUTPUTS_DIR, "overlays")
PORT          = int(os.environ.get("PORT", 5050))


def _resolve_api_key() -> Optional[str]:
    """
    Resolve the API key with two-tier lookup:

    1. Direct env-var (local development and CI):
       ZIWAVISION_API_KEY or VERIFY_API_KEY

    2. SSM Parameter Store (Lambda production deployment):
       The SAM template passes ZIWAVISION_API_KEY_PARAM containing the SSM
       parameter *name* (e.g. /ziwavision/prod/api-key).  The Lambda IAM role
       is granted ssm:GetParameter + kms:Decrypt on that path.
       This keeps the actual secret out of CloudFormation events and Lambda
       environment variable plaintext listings.

    Returns the key string if ≥ 16 characters, else None (fail-closed).
    """
    # Tier 1: plain env-var (dev / CI)
    raw = os.environ.get("ZIWAVISION_API_KEY") or os.environ.get("VERIFY_API_KEY")
    if raw and len(raw.strip()) >= 16:
        return raw.strip()

    # Tier 2: SSM (Lambda container in production)
    param_name = os.environ.get("ZIWAVISION_API_KEY_PARAM")
    if param_name:
        try:
            import boto3  # noqa: PLC0415
            ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
            resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
            value = resp["Parameter"]["Value"].strip()
            if len(value) >= 16:
                return value
            print(
                f"WARNING: SSM parameter {param_name!r} returned a value shorter than "
                "16 characters; treating as unconfigured."
            )
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: Failed to fetch API key from SSM ({param_name!r}): {exc}")

    return None


# Auth: fail closed.  If neither env-var nor SSM yields a valid key the API
# starts but all human-review endpoints return 503.
VERIFY_API_KEY: Optional[str] = _resolve_api_key()
_AUTH_CONFIGURED = VERIFY_API_KEY is not None

if not _AUTH_CONFIGURED:
    print(
        "WARNING: ZIWAVISION_API_KEY is not set (or < 16 chars) and SSM lookup failed. "
        "Human-review endpoints will fail closed (HTTP 503) until properly configured."
    )

# S3 — set by the SAM template via environment variables.
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")
S3_RESULTS_KEY = "data/results.json"
S3_RUNS_PREFIX = "runs/"

# Autonomous agent statuses (never verified / rejected)
_AGENT_STATUSES = frozenset(
    {"candidate", "needs_verification", "uncertain", "rejected_as_artefact",
     # legacy values written by earlier pipeline runs — kept for backward compat
     "needs_review", "skipped"}
)
# Statuses only a human reviewer may set
_HUMAN_FINAL_STATUSES = frozenset({"verified", "rejected"})

# Only pending candidate detections can receive human review
_ELIGIBLE_FOR_VERIFICATION = frozenset(
    {"needs_verification", "needs_review", "candidate", "uncertain"}
)

# Maximum reviewer notes length
_NOTES_MAX_LEN = 1000

app = Flask(__name__)
CORS(app)


# ── S3 / local persistence ─────────────────────────────────────────────────────

def _s3_client():
    import boto3  # noqa: PLC0415
    return boto3.client("s3")


def _load_results() -> list:
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            obj = s3.get_object(Bucket=RESULTS_BUCKET, Key=S3_RESULTS_KEY)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"S3 _load_results failed ({exc}); falling back to local file")
    if not os.path.exists(RESULTS_PATH):
        return []
    with open(RESULTS_PATH) as f:
        return json.load(f)


def _save_results(results: list) -> None:
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
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        f.write(payload)


RUNS_DIR = os.path.join(OUTPUTS_DIR, "runs")


def _save_run(run_data: dict) -> None:
    run_id = run_data["run_id"]
    payload = json.dumps(run_data, indent=2)
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=f"{S3_RUNS_PREFIX}{run_id}.json",
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"S3 _save_run failed ({exc}); saving locally")
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(os.path.join(RUNS_DIR, f"{run_id}.json"), "w") as f:
        f.write(payload)


def _load_run(run_id: str) -> Optional[dict]:
    if RESULTS_BUCKET:
        try:
            s3 = _s3_client()
            obj = s3.get_object(Bucket=RESULTS_BUCKET, Key=f"{S3_RUNS_PREFIX}{run_id}.json")
            return json.loads(obj["Body"].read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            pass
    path = os.path.join(RUNS_DIR, f"{run_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _list_runs() -> list:
    runs = []
    if os.path.exists(RUNS_DIR):
        for fname in sorted(os.listdir(RUNS_DIR), reverse=True):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(RUNS_DIR, fname)) as f:
                        runs.append(json.load(f))
                except Exception:
                    continue
    return runs



# ── stable hotspot ID ──────────────────────────────────────────────────────────

def _hotspot_id(entry: dict) -> str:
    """
    Derive a stable, URL-safe hotspot ID from the entry.

    Priority: use scene_id if present (already unique per Sentinel-2 granule).
    Fallback: derive from date + location hash so IDs remain stable across runs.
    The ID is lowercased and non-alphanumeric characters replaced with hyphens.
    """
    raw = entry.get("scene_id") or entry.get("date", "unknown")
    slug = raw.lower()
    # replace anything that is not alphanumeric, dot, or underscore with hyphen
    import re
    slug = re.sub(r"[^a-z0-9._]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _find_by_id(results: list, hotspot_id: str) -> Optional[dict]:
    for entry in results:
        if _hotspot_id(entry) == hotspot_id:
            return entry
    return None


def _entry_with_id(entry: dict) -> dict:
    """Return a copy of the entry with its hotspot_id injected."""
    return {**entry, "hotspot_id": _hotspot_id(entry)}


# ── authentication ─────────────────────────────────────────────────────────────

def _check_auth() -> bool:
    """
    Validate Bearer token or X-API-Key header using constant-time comparison.
    Returns False (not 503) so callers can distinguish misconfiguration from
    bad credentials.
    """
    if not _AUTH_CONFIGURED or not VERIFY_API_KEY:
        return False
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif api_key_header:
        token = api_key_header.strip()
    if not token:
        return False
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(
        token.encode("utf-8"),
        VERIFY_API_KEY.encode("utf-8"),
    )


def _auth_error_response():
    """Return the appropriate 401/503 based on configuration state."""
    if not _AUTH_CONFIGURED:
        return jsonify({
            "ok": False,
            "error": "Human-review authentication is not configured on this server.",
            "authenticated": False,
            "configured": False,
        }), 503
    return jsonify({
        "ok": False,
        "error": "Unauthorized: valid reviewer credentials required.",
        "authenticated": False,
        "configured": True,
    }), 401


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "ZiwaVision API",
        "auth_configured": _AUTH_CONFIGURED,
    })


@app.get("/api/hotspots")
def get_hotspots():
    """Return all scene results, sorted by date descending, each with hotspot_id."""
    results = _load_results()
    results.sort(key=lambda r: r.get("date", ""), reverse=True)
    return jsonify([_entry_with_id(r) for r in results])


# ── date-based lookup (moved from /api/hotspots/<date> to avoid route conflict) ──

@app.get("/api/hotspots/by-date/<date>")
def get_hotspot_by_date(date: str):
    """Return the result for a single acquisition date (YYYY-MM-DD)."""
    results = _load_results()
    entry = next((r for r in results if r.get("date") == date), None)
    if entry is None:
        abort(404, description=f"No result found for date {date!r}")
    return jsonify(_entry_with_id(entry))


# ── hotspot ID-based lookup ────────────────────────────────────────────────────

@app.get("/api/hotspots/<hotspot_id>")
def get_hotspot(hotspot_id: str):
    """
    Return a single hotspot by stable ID, with its full inspection trace attached.

    Response shape:
      {hotspot_id, scene_id, date, location, bbox,
       image_quality, cloud_fraction, unclassified_fraction,
       n_patches, total_area_ha, lake_area_ha,
       mean_patch_confidence, scene_iou, mean_patch_iou, n_in_reference,
       action, agent_reason, verification_status, decided_at,
       overlay_filename?, patch_details[], trace[]}
    """
    results = _load_results()
    entry = _find_by_id(results, hotspot_id)
    if entry is None:
        return jsonify({
            "ok": False,
            "error": f"Hotspot {hotspot_id!r} not found.",
        }), 404

    # Attach persisted trace records for this scene's date
    date = entry.get("date", "")
    traces = load_traces(date) if date else []

    payload = {**_entry_with_id(entry), "trace": traces}
    return jsonify(payload)


# ── human-review verification (ID-based) ──────────────────────────────────────

@app.post("/api/hotspots/<hotspot_id>/verify")
def verify_hotspot(hotspot_id: str):
    """
    Authenticated human-review endpoint.

    Only this path may set verification_status to 'verified' or 'rejected'.

    Required headers:
      Authorization: Bearer <ZIWAVISION_API_KEY>
      Content-Type:  application/json

    Required body fields:
      decision  string  — exactly 'verified' or 'rejected'

    Optional body fields:
      notes     string  — reviewer notes (max 1000 chars)

    Enforced rules
    ──────────────
    • Hotspot must exist.
    • Body must be valid JSON.
    • decision must be 'verified' or 'rejected' (nothing else).
    • Authentication must succeed.
    • The current status must be eligible (needs_review or needs_verification
      or candidate; not already a final human decision unless explicitly
      re-reviewing).
    • Repeated identical decision: returns 200 with a note; no mutation.
    • Conflicting re-review (e.g. change from verified → rejected): permitted
      with explicit re-review flag in the body.
    • reviewer_id is logged for attribution; credentials are never logged.
    """
    if not _check_auth():
        return _auth_error_response()

    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({
            "ok": False,
            "error": "Request body must be valid JSON with at least a 'decision' field.",
        }), 400

    decision = body.get("decision")
    if decision not in _HUMAN_FINAL_STATUSES:
        return jsonify({
            "ok": False,
            "error": (
                f"Invalid decision {decision!r}. "
                f"Only {sorted(_HUMAN_FINAL_STATUSES)} are permitted via this endpoint. "
                "Autonomous agent statuses cannot be set here."
            ),
            "allowed": sorted(_HUMAN_FINAL_STATUSES),
        }), 422

    notes = body.get("notes", "")
    if not isinstance(notes, str):
        return jsonify({"ok": False, "error": "'notes' must be a string."}), 400
    if len(notes) > _NOTES_MAX_LEN:
        return jsonify({
            "ok": False,
            "error": f"'notes' exceeds maximum length of {_NOTES_MAX_LEN} characters.",
        }), 400

    reviewer_id = body.get("reviewer_id", "anonymous")
    if not isinstance(reviewer_id, str):
        reviewer_id = "anonymous"
    re_review = bool(body.get("re_review", False))

    results = _load_results()
    entry = _find_by_id(results, hotspot_id)
    if entry is None:
        return jsonify({
            "ok": False,
            "error": f"Hotspot {hotspot_id!r} not found.",
        }), 404

    prev_status = entry.get("verification_status", "unknown")

    # Repeated identical decision → no-op
    if prev_status == decision:
        return jsonify({
            "ok": True,
            "note": f"Hotspot is already {decision!r}. No change applied.",
            "updated": _entry_with_id(entry),
            "authenticated": True,
        }), 200

    # Enforce allowed state transitions:
    # 1. Final human decision (verified / rejected) may be updated only with explicit re_review flag
    if prev_status in _HUMAN_FINAL_STATUSES:
        if not re_review:
            return jsonify({
                "ok": False,
                "error": (
                    f"Hotspot already has a final human-review status ({prev_status!r}). "
                    "Set 're_review: true' in the request body to override."
                ),
                "current_status": prev_status,
            }), 409
    # 2. Only pending candidate detections are eligible for human verification
    elif prev_status not in _ELIGIBLE_FOR_VERIFICATION:
        return jsonify({
            "ok": False,
            "error": (
                f"Hotspot {hotspot_id!r} with status {prev_status!r} is not eligible for human verification. "
                f"Only pending candidate detections ({sorted(_ELIGIBLE_FOR_VERIFICATION)}) can be verified or rejected. "
                "Records with status 'skipped', 'no_candidate', or failure states cannot receive human review."
            ),
            "current_status": prev_status,
            "eligible_statuses": sorted(_ELIGIBLE_FOR_VERIFICATION),
        }), 422

    # Apply
    date = entry.get("date", "")
    entry["verification_status"] = decision
    entry["verified_at"] = _utc_now()
    if notes:
        entry["reviewer_notes"] = notes

    _save_results(results)

    # Write audit trace — reviewer_id for attribution, no credentials
    trace_rec = TraceRecord(
        scene_id=entry.get("scene_id", "unknown"),
        date=date,
        location=entry.get("location", "Dunga Beach, Winam Gulf"),
        step=99,
        observation={
            "previous_status": prev_status,
            "hotspot_id": hotspot_id,
            "has_notes": bool(notes),
        },
        decision=f"human_{decision}",
        rule="Authenticated human reviewer decision via POST /api/hotspots/<id>/verify",
        outcome=(
            f"Candidate floating vegetation status changed from {prev_status!r} "
            f"to {decision!r} by reviewer {reviewer_id!r}."
        ),
        reassessment={"verification_status": decision, "reviewer_id": reviewer_id},
    )
    append_trace(trace_rec)

    return jsonify({
        "ok": True,
        "updated": _entry_with_id(entry),
        "previous_status": prev_status,
        "new_status": decision,
        "authenticated": True,
        "reviewer_id": reviewer_id,
    }), 200


# ── legacy /api/verify (backward compat with existing dashboard) ───────────────

@app.post("/api/verify")
def verify_legacy():
    """
    Legacy human verification endpoint — kept so the existing dashboard continues
    to work without a rebuild.

    Accepts the old body shape: {date, verified, patch_id?, status?}
    Only 'verified' and 'rejected' may be set via this authenticated path.
    'uncertain' and other agent statuses are accepted here for the legacy
    uncertain/flag workflow only (status field).

    For new integrations use POST /api/hotspots/<id>/verify.
    """
    if not _check_auth():
        return _auth_error_response()

    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Request body must be JSON")

    date = body.get("date")
    verified = body.get("verified")
    patch_id = body.get("patch_id")
    status = body.get("status")

    if date is None:
        abort(400, description="'date' is required")
    if verified is None and status is None:
        abort(400, description="Either 'verified' or 'status' is required")

    # Resolve the status to write
    resolved_status: str
    if status is not None:
        resolved_status = str(status)
    else:
        resolved_status = "verified" if verified else "uncertain"

    results = _load_results()
    entry = next((r for r in results if r.get("date") == date), None)
    if entry is None:
        abort(404, description=f"No result found for date {date!r}")

    prev_status = entry.get("verification_status", "unknown")
    if prev_status in _HUMAN_FINAL_STATUSES and not body.get("re_review"):
        return jsonify({
            "ok": False,
            "error": f"Hotspot already has a final human-review status ({prev_status!r}). Set 're_review: true' to override.",
            "current_status": prev_status,
        }), 409
    if prev_status not in _ELIGIBLE_FOR_VERIFICATION and prev_status not in _HUMAN_FINAL_STATUSES:
        return jsonify({
            "ok": False,
            "error": (
                f"Hotspot on date {date!r} with status {prev_status!r} is not eligible for human verification. "
                f"Only pending candidate detections ({sorted(_ELIGIBLE_FOR_VERIFICATION)}) can be verified or rejected."
            ),
            "current_status": prev_status,
            "eligible_statuses": sorted(_ELIGIBLE_FOR_VERIFICATION),
        }), 422

    results = apply_verification(results, date, patch_id, bool(verified), status=resolved_status)
    _save_results(results)

    updated = next((r for r in results if r.get("date") == date), None)

    trace_rec = TraceRecord(
        scene_id=updated.get("scene_id", "unknown") if updated else "unknown",
        date=date,
        location=updated.get("location", "Dunga Beach, Winam Gulf") if updated else "Dunga Beach, Winam Gulf",
        step=99,
        observation={"verified": bool(verified), "patch_id": patch_id, "status": resolved_status},
        decision=f"human_{resolved_status}",
        rule="Authenticated human review via legacy POST /api/verify",
        outcome=f"Candidate floating vegetation status set to {resolved_status!r} by authorized reviewer.",
        reassessment={"verification_status": resolved_status},
    )
    append_trace(trace_rec)

    return jsonify({
        "ok": True,
        "updated": _entry_with_id(updated) if updated else None,
        "authenticated": True,
    })


# ── inspect & asynchronous runs ────────────────────────────────────────────────

def _run_inspection_worker(run_id: str, target_date: str, bbox: Optional[list]) -> None:
    try:
        import inspect
        sig = inspect.signature(run_live_inspection)
        if "run_id" in sig.parameters:
            result = run_live_inspection(target_date, bbox=bbox, run_id=run_id)
        else:
            result = run_live_inspection(target_date, bbox=bbox)
        if result.get("ok"):
            hotspot_entry = result["hotspot"]
            results = _load_results()
            existing_idx = next((i for i, r in enumerate(results) if r.get("date") == target_date), -1)
            if existing_idx >= 0:
                results[existing_idx] = hotspot_entry
            else:
                results.append(hotspot_entry)
            _save_results(results)
            _save_run({
                "run_id": run_id,
                "date": target_date,
                "bbox": bbox,
                "status": "completed",
                "completed_at": _utc_now(),
                "result": result,
                "hotspot": hotspot_entry,
                "error": None,
            })
        else:
            _save_run({
                "run_id": run_id,
                "date": target_date,
                "bbox": bbox,
                "status": "failed",
                "completed_at": _utc_now(),
                "result": result,
                "hotspot": None,
                "error": result.get("error", "Inspection failed"),
            })
    except Exception as exc:  # noqa: BLE001
        _save_run({
            "run_id": run_id,
            "date": target_date,
            "bbox": bbox,
            "status": "failed",
            "completed_at": _utc_now(),
            "result": None,
            "hotspot": None,
            "error": str(exc),
        })


@app.post("/api/inspect")
@app.post("/api/inspect/<date>")
def inspect_scene(date: Optional[str] = None):
    """
    Active Inspector endpoint connected to live Earth Search → satellite asset → OpenCV pipeline.
    Supports asynchronous execution with durable job tracking via /api/runs/<run_id>.
    Returns 202 Accepted with poll_url unless sync=true is explicitly requested.
    """
    body = request.get_json(silent=True) or {}
    target_date = date or body.get("date")
    if not target_date:
        abort(400, description="'date' parameter is required (in URL or JSON body {'date': 'YYYY-MM-DD'})")

    bbox = body.get("bbox")
    is_sync = (
        request.args.get("sync", "").lower() in ("true", "1")
        or body.get("sync") is True
        or app.config.get("TESTING", False)
    )

    run_id = uuid.uuid4().hex[:12]
    run_data = {
        "run_id": run_id,
        "date": target_date,
        "bbox": bbox,
        "status": "running",
        "started_at": _utc_now(),
        "completed_at": None,
        "result": None,
        "hotspot": None,
        "error": None,
    }
    _save_run(run_data)

    if is_sync:
        _run_inspection_worker(run_id, target_date, bbox)
        final_run = _load_run(run_id) or run_data
        if final_run.get("status") == "completed":
            return jsonify(final_run["result"]), 200
        res = final_run.get("result") or {"ok": False, "error": final_run.get("error")}
        status_code = 404 if (final_run.get("result") or {}).get("status") == "scene_unavailable" else 502
        return jsonify(res), status_code

    import threading
    t = threading.Thread(target=_run_inspection_worker, args=(run_id, target_date, bbox), daemon=True)
    t.start()

    return jsonify({
        "ok": True,
        "run_id": run_id,
        "status": "running",
        "date": target_date,
        "poll_url": f"/api/runs/{run_id}",
    }), 202


@app.get("/api/runs/<run_id>")
def get_run(run_id: str):
    """Retrieve the current state and results of an inspection run."""
    run = _load_run(run_id)
    if run is None:
        return jsonify({"ok": False, "error": f"Run {run_id!r} not found."}), 404
    return jsonify(run), 200


@app.get("/api/runs")
def list_runs():
    """List recent inspection runs so active, completed, and failed jobs are observable."""
    return jsonify(_list_runs()), 200


# ── traces ─────────────────────────────────────────────────────────────────────

@app.get("/api/traces/<date>")
def get_traces(date: str):
    """Serve all persisted audit trace records for a given date."""
    records = load_traces(date)
    return jsonify({"date": date, "traces": records})


# ── overlay ────────────────────────────────────────────────────────────────────

@app.get("/api/overlay/<date>")
def get_overlay(date: str):
    safe_date = date.replace("..", "").replace("/", "")
    path = os.path.join(OVERLAYS_DIR, f"{safe_date}.png")
    if not os.path.exists(path):
        abort(404, description=f"No overlay image for date {date!r}")
    return send_file(path, mimetype="image/png")


# ── reference ──────────────────────────────────────────────────────────────────

@app.get("/api/reference")
def get_reference():
    ref_path = os.path.join(OUTPUTS_DIR, "reference_labels.json")
    if not os.path.exists(ref_path):
        return jsonify({"patches": [], "note": "reference not yet built"})
    with open(ref_path) as f:
        return jsonify(json.load(f))


# ── helpers ────────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── Lambda handler ─────────────────────────────────────────────────────────────
#
# Mangum 0.17+ is ASGI-only.  Flask is a WSGI application.
# Without an explicit WSGI→ASGI bridge, Mangum.Mangum(app) constructs without
# error but raises RuntimeError ("unable to infer a handler") on every real
# Lambda invocation because it cannot detect the event type from a WSGI callable.
#
# Fix: wrap Flask in a2wsgi.WSGIMiddleware (an ASGI adapter) before passing
# to Mangum.  lifespan='off' disables the ASGI lifespan protocol, which Flask
# does not implement.
try:
    from a2wsgi import WSGIMiddleware
    from mangum import Mangum
    handler = Mangum(WSGIMiddleware(app), lifespan="off")
except ImportError:
    handler = None


# ── local dev server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(RESULTS_PATH):
        print(f"WARNING: {RESULTS_PATH} not found.")
        print("Run 'python src/run_pipeline.py' first to generate results.")
    print(f"Starting ZiwaVision API on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
