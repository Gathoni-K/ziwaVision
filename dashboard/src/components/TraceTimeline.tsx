import React from 'react';
import { AgentAction } from '../types/hotspot';

interface TraceTimelineProps {
  action: AgentAction;
  reason: string;
  decidedAt?: string;
  imageQuality: number;
  confidence: number;
  sceneIou: number;
}

const ACTION_DESCRIPTIONS: Record<AgentAction, { title: string; color: string }> = {
  request_human_verification: {
    title: 'Request Human Verification',
    color: '#00e5a0',
  },
  process_another_observation: {
    title: 'Process Another Observation Date',
    color: '#fbbf24',
  },
  flag_uncertain: {
    title: 'Flag as Uncertain',
    color: '#ff6b6b',
  },
};

export const TraceTimeline: React.FC<TraceTimelineProps> = ({
  action,
  reason,
  decidedAt,
  imageQuality,
  confidence,
  sceneIou,
}) => {
  const meta = ACTION_DESCRIPTIONS[action] || {
    title: action,
    color: 'var(--text)',
  };

  const formattedTime = decidedAt ? new Date(decidedAt).toLocaleString() : 'Recent run';

  return (
    <div
      className="detail-reason"
      role="region"
      aria-label="Agent decision audit trace"
      style={{ borderLeftColor: meta.color }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
        <strong style={{ color: meta.color, fontSize: '0.85rem' }}>
          🤖 Agent Decision: {meta.title}
        </strong>
        <span style={{ fontSize: '0.70rem', color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
          {formattedTime}
        </span>
      </div>

      <p style={{ margin: '6px 0 10px 0', color: 'var(--text)', lineHeight: 1.5 }}>
        {reason || 'No explanation recorded by vision agent.'}
      </p>

      <div
        style={{
          display: 'flex',
          gap: '12px',
          paddingTop: '6px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          fontSize: '0.72rem',
          color: 'var(--muted)',
        }}
      >
        <span>
          Quality Score: <strong style={{ color: 'var(--text)' }}>{(imageQuality * 100).toFixed(0)}%</strong>
        </span>
        <span>•</span>
        <span>
          Confidence: <strong style={{ color: 'var(--text)' }}>{(confidence * 100).toFixed(0)}%</strong>
        </span>
        <span>•</span>
        <span>
          IoU vs Baseline: <strong style={{ color: 'var(--text)' }}>{sceneIou.toFixed(3)}</strong>
        </span>
      </div>
    </div>
  );
};
