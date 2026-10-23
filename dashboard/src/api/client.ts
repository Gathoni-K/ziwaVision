import { Hotspot, VerifyPayload, VerifyResponse } from '../types/hotspot';

/**
 * Centralized typed API client for ZiwaVision.
 *
 * Configured via VITE_API_BASE_URL environment variable.
 * Defaults to http://localhost:5050 in local development.
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050').replace(/\/$/, '');

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

export async function verifyHotspot(payload: VerifyPayload): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE}/api/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Verification request failed: HTTP ${res.status}`);
  }
  return res.json();
}

export function getOverlayUrl(date: string): string {
  return `${API_BASE}/api/overlay/${encodeURIComponent(date)}`;
}
