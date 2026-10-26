import React from 'react';
import { Hotspot } from '../types/hotspot';

interface StatsRowProps {
  hotspots: Hotspot[];
  isSampleData?: boolean;
}

export const StatsRow: React.FC<StatsRowProps> = ({ hotspots, isSampleData = false }) => {
  const totalScenes = hotspots.length;
  const totalPatches = hotspots.reduce((sum, h) => sum + (h.n_patches || 0), 0);
  const totalArea = hotspots.reduce((sum, h) => sum + (h.total_area_ha || 0), 0);
  const needsReview = hotspots.filter((h) => h.verification_status === 'needs_review').length;

  return (
    <div className="stats-row" role="region" aria-label="Summary statistics">
      <div className="stat-card" style={{ position: 'relative' }}>
        {isSampleData && (
          <span style={{
            position: 'absolute',
            top: '8px',
            right: '8px',
            background: '#f59e0b',
            color: '#000',
            fontWeight: 800,
            fontSize: '0.62rem',
            padding: '2px 6px',
            borderRadius: '3px',
            letterSpacing: '0.05em'
          }}>SAMPLE DATA</span>
        )}
        <div className="label">Scenes Processed</div>
        <div className="value">{totalScenes}</div>
        <div className="sub">clear observations</div>
      </div>
      <div className="stat-card">
        <div className="label">Candidate Patches</div>
        <div className="value">{totalPatches}</div>
        <div className="sub">detected in lake</div>
      </div>
      <div className="stat-card">
        <div className="label">Total Area</div>
        <div className="value">{totalArea.toFixed(1)}</div>
        <div className="sub">hectares (est. 10m px)</div>
      </div>
      <div className="stat-card">
        <div className="label">Needs Review</div>
        <div className="value">{needsReview}</div>
        <div className="sub">awaiting verification</div>
      </div>
    </div>
  );
};
