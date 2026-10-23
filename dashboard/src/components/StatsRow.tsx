import React from 'react';
import { Hotspot } from '../types/hotspot';

interface StatsRowProps {
  hotspots: Hotspot[];
}

export const StatsRow: React.FC<StatsRowProps> = ({ hotspots }) => {
  const totalScenes = hotspots.length;
  const totalPatches = hotspots.reduce((sum, h) => sum + (h.n_patches || 0), 0);
  const totalArea = hotspots.reduce((sum, h) => sum + (h.total_area_ha || 0), 0);
  const needsReview = hotspots.filter((h) => h.verification_status === 'needs_review').length;

  return (
    <div className="stats-row" role="region" aria-label="Summary statistics">
      <div className="stat-card">
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
