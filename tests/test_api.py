"""
test_api.py — Integration tests for the ZiwaVision Flask REST API.

Covers:
  A. GET /api/hotspots                   — list all
  B. GET /api/hotspots/<id>              — detail with trace
  C. GET /api/hotspots/<id> (missing)    — 404
  D. GET /api/hotspots/by-date/<date>    — date-based lookup
  E. POST /api/hotspots/<id>/verify      — human review endpoint
       - missing auth → 401/503
       - invalid token → 401
       - malformed body → 400
       - invalid decision values → 422
       - valid verified decision → 200 + trace written
       - valid rejected decision → 200 + trace written
       - repeated identical decision → 200 + no-op note
       - conflicting re-review without flag → 409
       - conflicting re-review with re_review=true → 200
       - agent-status values rejected → 422
  F. POST /api/verify (legacy)           — backward compat
  G. GET /api/traces/<date>              — trace retrieval
  H. GET /health                         — liveness + auth_configured field
  I. POST /api/inspect                   — explicit failure state
  J. Persisted state is not mutated by unauthenticated requests
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import api as api_module
from api import app, VERIFY_API_KEY, _hotspot_id
from trace import TraceRecord, append_trace, load_traces


# ── fixtures ───────────────────────────────────────────────────────────────────

SAMPLE_RESULTS = [
    {
        "scene_id": "S2B_36MXE_20260907_0_L2A",
        "date": "2026-09-07",
        "location": "Dunga Beach, Winam Gulf",
        "image_quality": 0.95,
        "cloud_fraction": 0.044,
        "n_patches": 4,
        "total_area_ha": 14.82,
        "lake_area_ha": 4610.0,
        "mean_patch_confidence": 0.72,
        "scene_iou": 0.184,
        "mean_patch_iou": 0.162,
        "n_in_reference": 3,
        "action": "request_human_verification",
        "agent_reason": "High confidence candidate floating vegetation.",
        "verification_status": "needs_review",
        "decided_at": "2026-09-07T10:32:00Z",
        "patch_details": [],
        "unclassified_fraction": 0.006,
    },
    {
        "scene_id": "S2A_36MXE_20260828_0_L2A",
        "date": "2026-08-28",
        "location": "Dunga Beach, Winam Gulf",
        "image_quality": 1.0,
        "cloud_fraction": 0.0,
        "n_patches": 0,
        "total_area_ha": 0.0,
        "lake_area_ha": 4610.0,
        "mean_patch_confidence": 0.0,
        "scene_iou": 0.0,
        "mean_patch_iou": 0.0,
        "n_in_reference": 0,
        "action": "process_another_observation",
        "agent_reason": "No candidate patches detected.",
        "verification_status": "skipped",
        "decided_at": "2026-08-28T10:30:00Z",
        "patch_details": [],
        "unclassified_fraction": 0.0,
    },
]

SAMPLE_ID_0 = _hotspot_id(SAMPLE_RESULTS[0])  # "s2b-36mxe-20260907-0-l2a"
SAMPLE_ID_1 = _hotspot_id(SAMPLE_RESULTS[1])


def _make_auth_header() -> dict:
    return {"Authorization": f"Bearer {VERIFY_API_KEY}"}


import copy

@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr(api_module, "_load_results", lambda: copy.deepcopy(SAMPLE_RESULTS))
    saved = []
    monkeypatch.setattr(api_module, "_save_results", lambda res: saved.extend(res))
    monkeypatch.setattr(api_module, "_AUTH_CONFIGURED", True)
    with app.test_client() as c:
        c._saved = saved
        yield c


@pytest.fixture
def client_no_auth(monkeypatch):
    """Simulates a server where ZIWAVISION_API_KEY is not configured."""
    app.config["TESTING"] = True
    monkeypatch.setattr(api_module, "_load_results", lambda: list(SAMPLE_RESULTS))
    monkeypatch.setattr(api_module, "_save_results", lambda res: None)
    monkeypatch.setattr(api_module, "_AUTH_CONFIGURED", False)
    monkeypatch.setattr(api_module, "VERIFY_API_KEY", None)
    with app.test_client() as c:
        yield c


# ── H. health ─────────────────────────────────────────────────────────────────

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "auth_configured" in data


# ── A. GET /api/hotspots ──────────────────────────────────────────────────────

def test_get_hotspots_returns_list_with_ids(client):
    res = client.get("/api/hotspots")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    for entry in data:
        assert "hotspot_id" in entry
        assert "scene_id" in entry
        assert "date" in entry


# ── D. GET /api/hotspots/by-date/<date> ──────────────────────────────────────

def test_get_hotspot_by_date_ok(client):
    res = client.get("/api/hotspots/by-date/2026-09-07")
    assert res.status_code == 200
    data = res.get_json()
    assert data["date"] == "2026-09-07"
    assert "hotspot_id" in data


def test_get_hotspot_by_date_missing(client):
    res = client.get("/api/hotspots/by-date/2000-01-01")
    assert res.status_code == 404


# ── B. GET /api/hotspots/<id> — detail ───────────────────────────────────────

def test_get_hotspot_detail_ok(client, monkeypatch):
    monkeypatch.setattr(api_module, "load_traces", lambda d: [{"scene_id": "S2B_36MXE_20260907_0_L2A", "step": 0}])
    res = client.get(f"/api/hotspots/{SAMPLE_ID_0}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["hotspot_id"] == SAMPLE_ID_0
    assert data["scene_id"] == "S2B_36MXE_20260907_0_L2A"
    assert data["date"] == "2026-09-07"
    # Trace must be attached
    assert "trace" in data
    assert isinstance(data["trace"], list)


def test_get_hotspot_detail_includes_all_measurement_fields(client, monkeypatch):
    """Detail response must include scene quality and detection measurements."""
    monkeypatch.setattr(api_module, "load_traces", lambda d: [])
    res = client.get(f"/api/hotspots/{SAMPLE_ID_0}")
    data = res.get_json()
    required = {
        "scene_id", "date", "location",
        "image_quality", "cloud_fraction", "n_patches",
        "total_area_ha", "mean_patch_confidence",
        "action", "agent_reason", "verification_status",
    }
    missing = required - set(data.keys())
    assert not missing, f"Detail response missing: {missing}"


# ── C. GET /api/hotspots/<id> — missing ──────────────────────────────────────

def test_get_hotspot_detail_unknown_id_returns_404(client, monkeypatch):
    monkeypatch.setattr(api_module, "load_traces", lambda d: [])
    res = client.get("/api/hotspots/this-id-does-not-exist-at-all")
    assert res.status_code == 404
    data = res.get_json()
    assert data["ok"] is False
    assert "not found" in data["error"].lower()


# ── E. POST /api/hotspots/<id>/verify ────────────────────────────────────────

# --- missing authentication ---

def test_verify_hotspot_no_auth_returns_401(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["authenticated"] is False


def test_verify_hotspot_unconfigured_returns_503(client_no_auth):
    res = client_no_auth.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
    )
    assert res.status_code == 503
    data = res.get_json()
    assert data["configured"] is False


def test_verify_hotspot_invalid_token_returns_401(client):
    headers = {"Authorization": "Bearer totally-wrong-token"}
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
        headers=headers,
    )
    assert res.status_code == 401


# --- malformed body ---

def test_verify_hotspot_no_body_returns_400(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        data="not-json",
        content_type="text/plain",
        headers=_make_auth_header(),
    )
    assert res.status_code == 400


def test_verify_hotspot_missing_decision_returns_400(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"notes": "forgot decision"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 422  # decision is None → not in permitted set


def test_verify_hotspot_notes_too_long_returns_400(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified", "notes": "x" * 1001},
        headers=_make_auth_header(),
    )
    assert res.status_code == 400


# --- invalid decision values ---

def test_verify_hotspot_agent_status_values_rejected(client):
    """Autonomous agent statuses must never be settable via the verify endpoint."""
    for bad_status in ["needs_review", "uncertain", "skipped", "candidate",
                       "rejected_as_artefact", "needs_verification"]:
        res = client.post(
            f"/api/hotspots/{SAMPLE_ID_0}/verify",
            json={"decision": bad_status},
            headers=_make_auth_header(),
        )
        assert res.status_code == 422, (
            f"Agent status {bad_status!r} should be rejected (422), got {res.status_code}"
        )
        data = res.get_json()
        assert "allowed" in data


def test_verify_hotspot_arbitrary_string_rejected(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "approve_and_publish"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 422


# --- missing hotspot ---

def test_verify_hotspot_nonexistent_id_returns_404(client):
    res = client.post(
        "/api/hotspots/this-id-does-not-exist/verify",
        json={"decision": "verified"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 404


# --- valid decisions ---

def test_verify_hotspot_verified_decision_succeeds(client):
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified", "reviewer_id": "reviewer_alice"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["authenticated"] is True
    assert data["new_status"] == "verified"
    assert data["previous_status"] == "needs_review"
    assert data["updated"]["verification_status"] == "verified"
    assert data["reviewer_id"] == "reviewer_alice"


def test_verify_hotspot_rejected_decision_succeeds(client):
    # Use SAMPLE_ID_1 whose status is 'skipped' (not a final human status)
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_1}/verify",
        json={"decision": "rejected"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["new_status"] == "rejected"


def test_verify_hotspot_writes_trace(client, monkeypatch, tmp_path):
    """A successful review must write a trace record to disk."""
    written_records = []

    # api.py uses `append_trace` resolved at call time from the `trace` module
    # it imported — monkeypatch it at the source module level.
    import trace as trace_mod
    monkeypatch.setattr(trace_mod, "append_trace",
                        lambda rec, traces_dir=None: written_records.append(rec))
    # Also patch in the api namespace (covers both import styles)
    monkeypatch.setattr(api_module, "append_trace",
                        lambda rec, traces_dir=None: written_records.append(rec))

    client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified", "reviewer_id": "bob"},
        headers=_make_auth_header(),
    )
    assert len(written_records) >= 1, (
        "verify endpoint must write at least one trace record"
    )
    rec = written_records[0]
    assert "human_verified" in rec.decision
    assert rec.observation.get("previous_status") == "needs_review"
    # Credentials must not appear in the trace
    assert VERIFY_API_KEY not in json.dumps(rec.to_dict())


# --- repeated / conflicting decisions ---

def test_verify_hotspot_repeated_identical_decision_is_noop(client, monkeypatch):
    """If the hotspot already has status=verified, sending verified again is a no-op 200."""
    already_verified = [
        {**SAMPLE_RESULTS[0], "verification_status": "verified"}
    ]
    monkeypatch.setattr(api_module, "_load_results", lambda: list(already_verified))
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "already" in data.get("note", "").lower()


def test_verify_hotspot_conflicting_redecision_requires_flag(client, monkeypatch):
    """Changing from verified → rejected without re_review=true must return 409."""
    already_verified = [
        {**SAMPLE_RESULTS[0], "verification_status": "verified"}
    ]
    monkeypatch.setattr(api_module, "_load_results", lambda: list(already_verified))
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "rejected"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 409
    data = res.get_json()
    assert "re_review" in data["error"]


def test_verify_hotspot_conflicting_redecision_with_flag_succeeds(client, monkeypatch):
    """With re_review=true the override is accepted."""
    already_verified = [
        {**SAMPLE_RESULTS[0], "verification_status": "verified"}
    ]
    monkeypatch.setattr(api_module, "_load_results", lambda: list(already_verified))
    res = client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "rejected", "re_review": True},
        headers=_make_auth_header(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["new_status"] == "rejected"


# ── J. Unauthenticated requests must not mutate state ─────────────────────────

def test_unauthenticated_request_does_not_mutate_state(client):
    """Without a valid token the results list must not be touched."""
    saved = client._saved
    client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
        # no auth header
    )
    assert len(saved) == 0, "Unauthenticated request must not write to persisted state"


def test_invalid_token_does_not_mutate_state(client):
    saved = client._saved
    client.post(
        f"/api/hotspots/{SAMPLE_ID_0}/verify",
        json={"decision": "verified"},
        headers={"Authorization": "Bearer bad-token-xyz"},
    )
    assert len(saved) == 0


# ── F. POST /api/verify (legacy) ─────────────────────────────────────────────

def test_legacy_verify_unauthorized(client):
    res = client.post("/api/verify", json={"date": "2026-09-07", "verified": True})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
    assert data["authenticated"] is False


def test_legacy_verify_authorized(client):
    res = client.post(
        "/api/verify",
        json={"date": "2026-09-07", "verified": True, "status": "verified"},
        headers=_make_auth_header(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["authenticated"] is True


def test_legacy_verify_invalid_token(client):
    res = client.post(
        "/api/verify",
        json={"date": "2026-09-07", "verified": True},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert res.status_code == 401


# ── G. GET /api/traces/<date> ─────────────────────────────────────────────────

def test_get_traces(client, monkeypatch):
    rec = TraceRecord(
        scene_id="S2A_TRACE_TEST",
        date="2026-09-07",
        location="Winam Gulf",
        step=0,
        observation={"quality": 0.98},
        decision="analyze_scene",
        rule="Initial observation",
        outcome="Detected 1 patch",
    )
    monkeypatch.setattr(api_module, "load_traces", lambda d: [rec.to_dict()])
    res = client.get("/api/traces/2026-09-07")
    assert res.status_code == 200
    data = res.get_json()
    assert data["date"] == "2026-09-07"
    assert len(data["traces"]) == 1
    assert data["traces"][0]["scene_id"] == "S2A_TRACE_TEST"


# ── I. POST /api/inspect ─────────────────────────────────────────────────────

def test_inspect_fault_handling(client, monkeypatch):
    def fail_inspection(date, bbox=None, location=None):
        return {
            "ok": False,
            "status": "scene_unavailable",
            "error": f"No Sentinel-2 L2A scene found on Earth Search for date {date}.",
            "traces": [
                {
                    "step": 0,
                    "decision": "access_failure",
                    "rule": "Earth Search lookup",
                    "outcome": "No scene available",
                }
            ],
        }

    monkeypatch.setattr(api_module, "run_live_inspection", fail_inspection)
    res = client.post("/api/inspect", json={"date": "2026-10-01"})
    assert res.status_code == 404
    data = res.get_json()
    assert data["ok"] is False
    assert data["status"] == "scene_unavailable"
    assert len(data["traces"]) == 1


def test_inspect_missing_date_returns_400(client):
    res = client.post("/api/inspect", json={"bbox": [34.73, -0.22, 34.83, -0.12]})
    assert res.status_code == 400


# ── Route compatibility: new routes don't break old callers ───────────────────

def test_old_hotspot_list_route_still_works(client):
    """GET /api/hotspots must still return the full list (used by dashboard)."""
    res = client.get("/api/hotspots")
    assert res.status_code == 200
    assert isinstance(res.get_json(), list)


def test_by_date_route_returns_correct_entry(client):
    res = client.get("/api/hotspots/by-date/2026-09-07")
    assert res.status_code == 200
    assert res.get_json()["scene_id"] == "S2B_36MXE_20260907_0_L2A"
