/**
 * Types matching the ZiwaVision API responses.
 *
 * Language rule: unverified detections are strictly "candidate floating vegetation",
 * never described as "hyacinth" until human verified.
 *
 * Status contract:
 *   Autonomous agent may set: candidate | needs_verification | uncertain |
 *                             rejected_as_artefact | needs_review | skipped
 *   Human reviewer may set:   verified | rejected (via authenticated endpoint only)
 */

/** All statuses the agent or a human reviewer may assign. */
export type VerificationStatus =
  // Agent-assigned (autonomous):
  | 'candidate'
  | 'needs_verification'
  | 'needs_review'         // legacy alias for needs_verification
  | 'uncertain'
  | 'rejected_as_artefact'
  | 'skipped'
  // Human-assigned only (via authenticated verify endpoint):
  | 'verified'
  | 'rejected';

/** The two statuses only a human reviewer may set. */
export type HumanDecision = 'verified' | 'rejected';

export type AgentAction =
  | 'request_human_verification'
  | 'process_another_observation'
  | 'flag_uncertain';

export interface PatchDetail {
  patch_id: number;
  area_ha: number;
  centroid_latlon: [number, number]; // [lat, lon]
  centroid_px: [number, number];     // [row, col]
  mean_ndvi: number;
  ndvi_fraction: number;
  scl_veg_fraction: number;
  confidence: number;
  reference_iou?: number;
  in_reference?: boolean;
  verified?: boolean;
}

export interface Hotspot {
  /** Stable URL-safe ID derived from scene_id. Injected by the API. */
  hotspot_id?: string;
  scene_id: string;
  date: string; // YYYY-MM-DD
  location: string;
  bbox: [number, number, number, number]; // [W, S, E, N]
  image_quality: number; // 0..1
  cloud_fraction: number;
  unclassified_fraction: number;
  n_patches: number;
  total_area_ha: number;
  lake_area_ha: number;
  mean_patch_confidence: number;
  scene_iou: number;
  mean_patch_iou: number;
  n_in_reference: number;
  action: AgentAction;
  agent_reason: string;
  verification_status: VerificationStatus;
  decided_at: string;
  overlay_path?: string;
  overlay_filename?: string;
  patch_details: PatchDetail[];
  verified_at?: string;
  reviewer_notes?: string;
  /** Attached inspection trace — present on GET /api/hotspots/<id> responses. */
  trace?: TraceEntry[];
}

export interface TraceEntry {
  scene_id?: string;
  date?: string;
  location?: string;
  step?: number;
  decision?: string;
  action?: AgentAction | string;
  rule?: string;
  outcome?: string;
  reason?: string;
  observation?: Record<string, any>;
  reassessment?: Record<string, any>;
  decided_at?: string;
  written_at?: string;
  image_quality?: number;
  detection_confidence?: number;
  reference_iou?: number;
}

export interface VerifyPayload {
  date: string;
  verified: boolean;
  patch_id?: number | null;
  status?: VerificationStatus;
}

export interface VerifyResponse {
  ok: boolean;
  updated: Hotspot;
  authenticated?: boolean;
  previous_status?: VerificationStatus;
  new_status?: VerificationStatus;
  reviewer_id?: string;
  note?: string;
}

export interface InspectResponse {
  ok: boolean;
  hotspot?: Hotspot;
  traces?: TraceEntry[];
  error?: string;
  status?: string;
  decision?: string;
}
