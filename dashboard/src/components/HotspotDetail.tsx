import React from 'react';
import { Hotspot, TraceEntry, VerificationStatus } from '../types/hotspot';
import { StatusBadge } from './StatusBadge';
import { OverlayViewer } from './OverlayViewer';
import { PatchCardList } from './PatchCardList';
import { TraceTimeline } from './TraceTimeline';
import { VerifyControls } from './VerifyControls';

interface HotspotDetailProps {
  hotspot: Hotspot | null;
  onClose: () => void;
  onVerify: (status: VerificationStatus) => void;
  isVerifying: boolean;
  isSampleData?: boolean;
  onInspect?: (date: string) => void;
  isInspecting?: boolean;
  inspectError?: string | null;
  traces?: TraceEntry[];
}

function getScoreColor(val?: number): string {
  if (val === undefined || val === null) return 'var(--muted)';
  if (val >= 0.7) return 'var(--accent)';
  if (val >= 0.4) return 'var(--warn)';
  return 'var(--danger)';
}

export const HotspotDetail: React.FC<HotspotDetailProps> = ({
  hotspot,
  onClose,
  onVerify,
  isVerifying,
  isSampleData = false,
  onInspect,
  isInspecting = false,
  inspectError = null,
  traces = [],
}) => {
  if (!hotspot) {
    return (
      <aside className="detail-panel empty" aria-label="Scene detail placeholder">
        <div className="empty-icon" aria-hidden="true">
          🛰️
        </div>
        <p>Select an observation date to inspect detections & agent decisions</p>
      </aside>
    );
  }

  return (
    <aside className="detail-panel" aria-label={`Detail for scene ${hotspot.date}`}>
      <div className="detail-header">
        <div className="detail-date">{hotspot.date}</div>
        {isSampleData && (
          <span
            style={{
              background: '#f59e0b',
              color: '#000',
              fontWeight: 800,
              fontSize: '0.65rem',
              padding: '2px 6px',
              borderRadius: '3px',
              letterSpacing: '0.05em',
            }}
          >
            SAMPLE DATA
          </span>
        )}
        <StatusBadge status={hotspot.verification_status} />
        <div className="spacer" />
        <button
          type="button"
          className="close-btn"
          onClick={onClose}
          aria-label="Close detail panel"
          title="Close detail panel (Esc)"
        >
          ✕
        </button>
      </div>

      {/* Satellite Imagery Overlay */}
      <OverlayViewer date={hotspot.date} />

      {/* Metric Chips */}
      <section className="detail-metrics" aria-label="Scene metrics">
        <div className="metric-chip">
          <div className="m-label">Image Quality</div>
          <div
            className="m-value"
            style={{ color: getScoreColor(hotspot.image_quality) }}
          >
            {(hotspot.image_quality * 100).toFixed(0)}%
          </div>
        </div>

        <div className="metric-chip">
          <div className="m-label">Detection Confidence</div>
          <div
            className="m-value"
            style={{ color: getScoreColor(hotspot.mean_patch_confidence) }}
          >
            {(hotspot.mean_patch_confidence * 100).toFixed(0)}%
          </div>
        </div>

        <div className="metric-chip">
          <div className="m-label">Candidate Patches</div>
          <div className="m-value">{hotspot.n_patches}</div>
        </div>

        <div className="metric-chip">
          <div className="m-label">Total Extent</div>
          <div className="m-value" style={{ color: 'var(--accent2)' }}>
            {hotspot.total_area_ha.toFixed(2)} ha
          </div>
        </div>

        <div className="metric-chip">
          <div className="m-label">Reference Baseline IoU</div>
          <div className="m-value">{hotspot.scene_iou.toFixed(3)}</div>
        </div>

        <div className="metric-chip">
          <div className="m-label">Lake Surface</div>
          <div className="m-value">
            {hotspot.lake_area_ha ? `${Math.round(hotspot.lake_area_ha)} ha` : '—'}
          </div>
        </div>
      </section>

      {/* Candidate Floating Vegetation List */}
      <PatchCardList patches={hotspot.patch_details || []} />

      {/* Active Inspector Trigger Bar */}
      <div
        style={{
          margin: '16px 0 12px 0',
          padding: '12px 14px',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text)' }}>
              ⚡ Active Inspector Live Pipeline
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>
              Earth Search STAC → Sentinel-2 COG → OpenCV 5 → Decision Gates
            </div>
          </div>
          {onInspect && (
            <button
              type="button"
              disabled={isInspecting}
              onClick={() => onInspect(hotspot.date)}
              style={{
                background: isInspecting ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg, #00e5a0, #00b37e)',
                color: isInspecting ? 'var(--muted)' : '#041f17',
                border: 'none',
                fontWeight: 700,
                fontSize: '0.78rem',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                cursor: isInspecting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              {isInspecting ? (
                <>
                  <span className="spinner" style={{ display: 'inline-block', width: '12px', height: '12px', border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  <span>Inspecting Live Scene…</span>
                </>
              ) : (
                <span>🔬 Run Active Inspector</span>
              )}
            </button>
          )}
        </div>

        {inspectError && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 12px',
              fontSize: '0.74rem',
              color: '#f87171',
              display: 'flex',
              gap: '6px',
              alignItems: 'flex-start',
            }}
          >
            <span>⚠️</span>
            <div>
              <strong>Live Inspection Failed:</strong> {inspectError}
            </div>
          </div>
        )}
      </div>

      {/* Agent Decision Trace */}
      <TraceTimeline
        action={hotspot.action}
        reason={hotspot.agent_reason}
        decidedAt={hotspot.decided_at}
        imageQuality={hotspot.image_quality}
        confidence={hotspot.mean_patch_confidence}
        sceneIou={hotspot.scene_iou}
        traces={traces}
      />

      {/* Action Controls */}
      <VerifyControls
        currentStatus={hotspot.verification_status}
        date={hotspot.date}
        isVerifying={isVerifying}
        onVerify={onVerify}
      />
    </aside>
  );
};
