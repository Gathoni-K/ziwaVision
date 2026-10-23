import React from 'react';
import { PatchDetail } from '../types/hotspot';

interface PatchCardListProps {
  patches: PatchDetail[];
}

export const PatchCardList: React.FC<PatchCardListProps> = ({ patches }) => {
  if (!patches || patches.length === 0) {
    return (
      <div className="detail-patches">
        <h3>Candidate Floating Vegetation</h3>
        <p style={{ color: 'var(--muted)', fontSize: '0.80rem', padding: '6px 0' }}>
          No discrete candidate vegetation patches detected in open lake for this observation.
        </p>
      </div>
    );
  }

  return (
    <div className="detail-patches" role="region" aria-label="Candidate floating vegetation patches">
      <h3>Candidate Floating Vegetation ({patches.length})</h3>
      {patches.map((p) => (
        <div key={p.patch_id} className="patch-card" id={`patch-${p.patch_id}`}>
          <div className="patch-row">
            <span className="patch-label">Patch #{p.patch_id}</span>
            <span className="patch-val" style={{ color: 'var(--accent2)', fontWeight: 600 }}>
              {p.area_ha.toFixed(2)} ha
            </span>
          </div>
          <div className="patch-row">
            <span className="patch-label">NDVI Mean</span>
            <span className="patch-val">{p.mean_ndvi.toFixed(3)}</span>
          </div>
          <div className="patch-row">
            <span className="patch-label">Detection Confidence</span>
            <span className="patch-val">{(p.confidence * 100).toFixed(0)}%</span>
          </div>
          {p.centroid_latlon && (
            <div className="patch-row">
              <span className="patch-label">Centroid Coordinates</span>
              <span className="patch-val">
                {p.centroid_latlon[0].toFixed(4)}, {p.centroid_latlon[1].toFixed(4)}
              </span>
            </div>
          )}
          {p.reference_iou !== undefined && (
            <div className="patch-row">
              <span className="patch-label">Reference Baseline IoU</span>
              <span className="patch-val">{p.reference_iou.toFixed(3)}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
