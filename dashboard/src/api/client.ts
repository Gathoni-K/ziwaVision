import { Hotspot, InspectResponse, TraceEntry, VerifyPayload, VerifyResponse } from '../types/hotspot';

/**
 * Centralized typed API client for ZiwaVision.
 *
 * Configured via VITE_API_BASE_URL and VITE_API_KEY environment variables.
 * Defaults to http://localhost:5050 in local development.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050').replace(/\/$/, '');
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

export async function fetchHotspot(date: string): Promise<Hotspot> {
  const res = await fetch(`${API_BASE}/api/hotspots/${encodeURIComponent(date)}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch hotspot for date ${date}: HTTP ${res.status}`);
  }
  return res.json();
}

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

