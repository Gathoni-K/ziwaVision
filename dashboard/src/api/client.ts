import { Hotspot, InspectResponse, TraceEntry, VerifyPayload, VerifyResponse } from '../types/hotspot';

/**
 * Centralized typed API client for ZiwaVision.
 *
 * Configured via VITE_API_BASE_URL and VITE_API_KEY environment variables.
 * Defaults to http://localhost:5050 in local development.
 *
 * Route changes (2026-10-26):
 *   - GET /api/hotspots/<date>  moved to  GET /api/hotspots/by-date/<date>
 *   - GET /api/hotspots/<id>    returns full hotspot with traces attached
 *   - POST /api/hotspots/<id>/verify  is the canonical human-review endpoint
 *   - POST /api/verify          remains for backward compat (legacy dashboard flows)
 *
 * Security: VITE_API_KEY is a development-only default.
 * In production the key must be injected at deploy time and must never be
 * committed to the repository or bundled into the public frontend.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050').replace(/\/$/, '');

// NOTE: embedding any secret in the compiled frontend is insecure.
// VITE_API_KEY is provided only for local development convenience.
// Production deployments must authenticate through a server-side proxy
// so that the reviewer key is never exposed to browser clients.
export const API_KEY = import.meta.env.VITE_API_KEY || 'ziwa-inspector-secret-2026';

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.status === 'ok';
  } catch {
    return false;
  }
}

export async function fetchHotspots(): Promise<Hotspot[]> {
  const res = await fetch(`${API_BASE}/api/hotspots`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch hotspots: HTTP ${res.status} (${res.statusText})`);
  }
  return res.json();
}

/**
 * Fetch a single hotspot by stable hotspot_id (scene-ID slug).
 * The response includes the attached inspection trace.
 */
export async function fetchHotspotById(hotspotId: string): Promise<Hotspot & { trace: TraceEntry[] }> {
  const res = await fetch(`${API_BASE}/api/hotspots/${encodeURIComponent(hotspotId)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Hotspot ${hotspotId} not found: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * @deprecated Use fetchHotspotById when the stable ID is available.
 * Retained for scenes that were fetched from the list without an ID.
 */
export async function fetchHotspotByDate(date: string): Promise<Hotspot> {
  const res = await fetch(`${API_BASE}/api/hotspots/by-date/${encodeURIComponent(date)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch hotspot for date ${date}: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Human-review verification via the canonical ID-based endpoint.
 * decision must be exactly 'verified' or 'rejected'.
 * Only authenticated requests with a valid reviewer key succeed.
 */
export async function verifyHotspotById(
  hotspotId: string,
  decision: 'verified' | 'rejected',
  options?: { notes?: string; reviewerId?: string; reReview?: boolean; apiKey?: string }
): Promise<VerifyResponse> {
  const token = options?.apiKey || API_KEY;
  const body: Record<string, unknown> = { decision };
  if (options?.notes)      body.notes       = options.notes;
  if (options?.reviewerId) body.reviewer_id = options.reviewerId;
  if (options?.reReview)   body.re_review   = true;

  const res = await fetch(`${API_BASE}/api/hotspots/${encodeURIComponent(hotspotId)}/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `Verification failed: HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Legacy verify — kept so existing dashboard flows continue working.
 * New code should prefer verifyHotspotById.
 */
export async function verifyHotspot(payload: VerifyPayload, apiKey?: string): Promise<VerifyResponse> {
  const token = apiKey || API_KEY;
  const res = await fetch(`${API_BASE}/api/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `Verification request failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function inspectScene(date: string, bbox?: number[]): Promise<InspectResponse> {
  const res = await fetch(`${API_BASE}/api/inspect`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ date, bbox }),
  });
  const data = await res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `Inspection failed with HTTP ${res.status}`);
  }
  return data;
}

export async function fetchTraces(date: string): Promise<TraceEntry[]> {
  try {
    const res = await fetch(`${API_BASE}/api/traces/${encodeURIComponent(date)}`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.traces || [];
  } catch {
    return [];
  }
}

export function getOverlayUrl(date: string): string {
  return `${API_BASE}/api/overlay/${encodeURIComponent(date)}`;
}
