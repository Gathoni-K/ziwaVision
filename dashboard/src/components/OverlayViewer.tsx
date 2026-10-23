import React, { useState } from 'react';
import { getOverlayUrl } from '../api/client';

interface OverlayViewerProps {
  date: string;
}

export const OverlayViewer: React.FC<OverlayViewerProps> = ({ date }) => {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const imgUrl = getOverlayUrl(date);

  return (
    <div className="detail-overlay" role="region" aria-label="Satellite imagery overlay">
      {isLoading && !hasError && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0d1520',
          }}
        >
          <div className="spinner" role="status" aria-label="Loading satellite overlay" />
        </div>
      )}

      {hasError ? (
        <div className="overlay-fallback">
          <p>
            🛰️ Overlay image not available for {date}.<br />
            <span style={{ fontSize: '0.72rem', color: '#4b5563', marginTop: '6px', display: 'block' }}>
              Run the pipeline (<code>python src/run_pipeline.py</code>) to render composite overlays.
            </span>
          </p>
        </div>
      ) : (
        <img
          src={imgUrl}
          alt={`Satellite overlay for ${date} — candidate floating vegetation highlighted in yellow`}
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setHasError(true);
          }}
          style={{ display: isLoading ? 'none' : 'block' }}
        />
      )}

      <div className="overlay-label">Sentinel-2 · Dunga Beach, Winam Gulf</div>
    </div>
  );
};
