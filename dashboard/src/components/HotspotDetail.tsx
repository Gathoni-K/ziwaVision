import React from 'react';
import { Hotspot, VerificationStatus } from '../types/hotspot';
import { StatusBadge } from './StatusBadge';
import { OverlayViewer } from './OverlayViewer';
import { PatchCardList } from './PatchCardList';
import { TraceTimeline } from './TraceTimeline';

interface HotspotDetailProps {
  hotspot: Hotspot | null;
  onClose: () => void;
  onVerify?: (status: VerificationStatus) => void;
  isVerifying?: boolean;
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
  isVerifying = false,
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

  const isVerified = hotspot.verification_status === 'verified';
  const isUncertain = hotspot.verification_status === 'uncertain';
  const isRejected = hotspot.verification_status === 'rejected';

  return (
    <aside className="detail-panel" aria-label={`Detail for scene ${hotspot.date}`}>
      <div className="detail-header">
        <div className="detail-date">{hotspot.date}</div>
        <StatusBadge status={hotspot.verification_status} />
        <div className="spacer" />
        <button
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
      <div className="detail-metrics" role="region" aria-label="Scene metrics">
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
      </div>

      {/* Candidate Floating Vegetation List */}
      <PatchCardList patches={hotspot.patch_details || []} />

      {/* Agent Decision Trace */}
      <TraceTimeline
        action={hotspot.action}
        reason={hotspot.agent_reason}
        decidedAt={hotspot.decided_at}
        imageQuality={hotspot.image_quality}
        confidence={hotspot.mean_patch_confidence}
        sceneIou={hotspot.scene_iou}
      />

      {/* Action Controls */}
      <div className="detail-actions" role="group" aria-label="Verification controls">
        <button
          className="btn-action btn-verify"
          disabled={isVerifying || isVerified}
          onClick={() => onVerify?.('verified')}
          aria-label={`Mark candidate vegetation as verified for ${hotspot.date}`}
        >
          {isVerified ? '✓ Verified' : '✓ Mark Verified'}
        </button>

        <button
          className="btn-action btn-uncertain"
          disabled={isVerifying || isUncertain}
          onClick={() => onVerify?.('uncertain')}
          aria-label={`Flag candidate vegetation as uncertain for ${hotspot.date}`}
        >
          {isUncertain ? '⚑ Uncertain' : '⚑ Flag Uncertain'}
        </button>

        <button
          className="btn-action btn-reject"
          disabled={isVerifying || isRejected}
          onClick={() => onVerify?.('rejected')}
          aria-label={`Reject candidate vegetation for ${hotspot.date}`}
        >
          {isRejected ? '✕ Rejected' : '✕ Reject'}
        </button>
      </div>
    </aside>
  );
};
