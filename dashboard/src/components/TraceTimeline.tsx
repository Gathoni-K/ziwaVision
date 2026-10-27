import React from 'react';
import { AgentAction, TraceEntry } from '../types/hotspot';

interface TraceTimelineProps {
  action: AgentAction;
  reason: string;
  decidedAt?: string;
  imageQuality: number;
  confidence: number;
  sceneIou: number;
  traces?: TraceEntry[];
}

const ACTION_COLORS: Record<string, string> = {
  request_human_verification: '#00e5a0',
  needs_verification: '#00e5a0',
  human_verified: '#00e5a0',
  process_another_observation: '#fbbf24',
  no_candidate: '#60a5fa',
  flag_uncertain: '#ff6b6b',
  reject_mask_artifact: '#f87171',
  access_failure: '#ef4444',
  asset_read_failure: '#ef4444',
  lake_mask_failed: '#ef4444',
  inspect_crop: '#38bdf8',
  alt_analysis: '#a78bfa',
  analyze_scene: '#818cf8',
  fetch_alternate_scene: '#fbbf24',
};

export const TraceTimeline: React.FC<TraceTimelineProps> = ({
  action,
  reason,
  decidedAt,
  imageQuality,
  confidence,
  sceneIou,
  traces,
}) => {
  const defaultColor = ACTION_COLORS[action] || 'var(--accent)';
  const formattedTime = decidedAt ? new Date(decidedAt).toLocaleString() : 'Recent run';

  return (
    <section
      className="detail-reason"
      aria-label="Agent decision audit trace"
      style={{ borderLeftColor: defaultColor }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <strong style={{ color: defaultColor, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>🤖</span>
          <span>Active Inspector Audit Trace</span>
        </strong>
        <span style={{ fontSize: '0.70rem', color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
          {formattedTime}
        </span>
      </div>

      {traces && traces.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
          {traces.map((tr, idx) => {
            const decColor = ACTION_COLORS[tr.decision || ''] || 'var(--text)';
            const traceKey =
              tr.written_at ||
              (tr.step !== undefined ? `${tr.scene_id ?? 'trace'}-step-${tr.step}` : null) ||
              `${tr.scene_id ?? 'trace'}-${tr.decision ?? 'decision'}-${tr.rule ?? ''}`;
            return (
              <div
                key={traceKey}
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 10px',
                  fontSize: '0.78rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 700, color: decColor }}>
                    Step {tr.step ?? idx}: {tr.decision}
                  </span>
                  {tr.written_at && (
                    <span style={{ fontSize: '0.68rem', color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                      {new Date(tr.written_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>

                {tr.rule && (
                  <div style={{ color: 'var(--muted)', fontSize: '0.72rem', marginBottom: '4px' }}>
                    <strong>Gate:</strong> {tr.rule}
                  </div>
                )}

                {tr.outcome && (
                  <div style={{ color: 'var(--text)', lineHeight: 1.4 }}>
                    <strong>Outcome:</strong> {tr.outcome}
                  </div>
                )}

                {tr.observation && Object.keys(tr.observation).length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '8px',
                      marginTop: '6px',
                      paddingTop: '4px',
                      borderTop: '1px dashed rgba(255, 255, 255, 0.08)',
                      fontSize: '0.70rem',
                      color: 'var(--muted)',
                      fontFamily: 'var(--mono)',
                    }}
                  >
                    {Object.entries(tr.observation).map(([k, v]) => (
                      <span key={k}>
                        {k}: <strong style={{ color: 'var(--text)' }}>{typeof v === 'number' ? (v > 10 ? v.toFixed(1) : v.toFixed(3)) : String(v)}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <>
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
        </>
      )}
    </section>
  );
};

