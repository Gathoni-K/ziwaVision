import type React from 'react';
import type { Hotspot } from '../types/hotspot';

interface AreaOverTimeChartProps {
  hotspots: Hotspot[];
  selectedDate?: string | null;
  onSelectDate?: (date: string) => void;
  isSampleData?: boolean;
}

export const AreaOverTimeChart: React.FC<AreaOverTimeChartProps> = ({
  hotspots,
  selectedDate,
  onSelectDate,
  isSampleData = false,
}) => {
  if (hotspots.length < 2) return null;

  // Sort chronological for chart
  const chronHotspots = [...hotspots].sort((a, b) => a.date.localeCompare(b.date));

  const width = 640;
  const height = 120;
  const padX = 40;
  const padY = 20;

  const maxArea = Math.max(...chronHotspots.map((h) => h.total_area_ha), 5);
  const chartW = width - padX * 2;
  const chartH = height - padY * 2;

  const points = chronHotspots.map((h, i) => {
    const x = padX + (i / (chronHotspots.length - 1)) * chartW;
    const y = height - padY - (h.total_area_ha / maxArea) * chartH;
    return { x, y, hotspot: h };
  });

  const lineD = points.reduce((acc, p, i) => {
    return `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }, '');

  const areaD = `${lineD} L ${points[points.length - 1].x.toFixed(1)},${height - padY} L ${points[0].x.toFixed(1)},${height - padY} Z`;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>📈</span>
          <span>Candidate Vegetation Extent Trend</span>
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
        </div>
        <div className="chart-sub">Area in hectares (ha) over observation dates</div>
      </div>
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          role="img"
          aria-label="Vegetation area trend over time"
        >
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00e5a0" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#00e5a0" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={padX}
            y1={height - padY}
            x2={width - padX}
            y2={height - padY}
            stroke="rgba(255,255,255,0.08)"
            strokeDasharray="4"
          />
          <line
            x1={padX}
            y1={padY}
            x2={width - padX}
            y2={padY}
            stroke="rgba(255,255,255,0.08)"
            strokeDasharray="4"
          />

          {/* Area under curve */}
          <path d={areaD} fill="url(#areaGradient)" />

          {/* Line */}
          <path
            d={lineD}
            fill="none"
            stroke="#00e5a0"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Data Points */}
          {points.map((p) => {
            const isSelected = p.hotspot.date === selectedDate;
            return (
              // biome-ignore lint/a11y/useSemanticElements: SVG g element cannot be replaced with an HTML button
              <g
                key={p.hotspot.date}
                role="button"
                tabIndex={0}
                aria-label={`Select observation date ${p.hotspot.date}`}
                style={{ cursor: onSelectDate ? 'pointer' : 'default', outline: 'none' }}
                onClick={() => onSelectDate?.(p.hotspot.date)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectDate?.(p.hotspot.date);
                  }
                }}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isSelected ? 6 : 4}
                  fill={isSelected ? '#c8f56a' : '#00e5a0'}
                  stroke="#0b0f1a"
                  strokeWidth="2"
                />
                <text
                  x={p.x}
                  y={height - 4}
                  textAnchor="middle"
                  fill="#6b7a99"
                  fontSize="9"
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {p.hotspot.date.slice(5)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
