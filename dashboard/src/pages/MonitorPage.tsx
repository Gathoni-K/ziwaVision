import React, { useState, useEffect, useCallback } from 'react';
import { useHotspots } from '../hooks/useHotspots';
import { useVerify } from '../hooks/useVerify';
import { Header } from '../components/Header';
import { StatsRow } from '../components/StatsRow';
import { AreaOverTimeChart } from '../components/AreaOverTimeChart';
import { HotspotList } from '../components/HotspotList';
import { HotspotDetail } from '../components/HotspotDetail';
import { Toast, ToastMessage } from '../components/Toast';
import { TraceEntry, VerificationStatus } from '../types/hotspot';
import { inspectScene, fetchTraces } from '../api/client';

export const MonitorPage: React.FC = () => {
  const {
    hotspots,
    isLoading,
    error,
    isApiConnected,
    isFallback,
    refetch,
    updateLocalHotspot,
  } = useHotspots();

  const { isVerifying, verify } = useVerify();

  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectError, setInspectError] = useState<string | null>(null);
  const [traces, setTraces] = useState<TraceEntry[]>([]);

  const addToast = useCallback(
    (type: 'success' | 'error' | 'info', message: string) => {
      const id = Date.now().toString() + Math.random().toString(36).slice(2, 6);
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    },
    []
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    if (!selectedDate && hotspots.length > 0) {
      const reviewItem = hotspots.find((h) => h.verification_status === 'needs_review' || h.verification_status === 'needs_verification');
      if (reviewItem) setSelectedDate(reviewItem.date);
    }
  }, [hotspots, selectedDate]);

  useEffect(() => {
    if (selectedDate) {
      setInspectError(null);
      fetchTraces(selectedDate).then((tr) => setTraces(tr));
    } else {
      setTraces([]);
      setInspectError(null);
    }
  }, [selectedDate]);

  const selectedHotspot = hotspots.find((h) => h.date === selectedDate) || null;

  const handleInspect = async (date: string) => {
    setIsInspecting(true);
    setInspectError(null);
    try {
      addToast('info', `Querying Earth Search for ${date}, retrieving Sentinel-2 scene and running computer vision analysis…`);
      const res = await inspectScene(date);
      if (res.ok && res.hotspot) {
        updateLocalHotspot(res.hotspot);
        if (res.traces) setTraces(res.traces);
        addToast('success', `Analysis complete for ${date}: ${res.decision || res.status}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Inspection failed';
      setInspectError(msg);
      addToast('error', `Analysis failed: ${msg}`);
      fetchTraces(date).then((tr) => setTraces(tr));
    } finally {
      setIsInspecting(false);
    }
  };

  const handleVerify = async (newStatus: VerificationStatus) => {
    if (!selectedHotspot) return;
    try {
      const updated = await verify(selectedHotspot, newStatus, isFallback);
      updateLocalHotspot(updated);
      fetchTraces(selectedHotspot.date).then((tr) => setTraces(tr));
      const statusLabels: Record<VerificationStatus, string> = {
        verified: 'marked as verified ✓',
        uncertain: 'flagged as uncertain ⚑',
        rejected: 'rejected ✕',
        needs_review: 'reset to needs review',
        skipped: 'skipped',
        candidate: 'candidate identified',
        needs_verification: 'pending human verification',
        rejected_as_artefact: 'rejected as analysis artefact',
      };
      addToast('success', `Scene ${selectedHotspot.date} ${statusLabels[newStatus] || newStatus}.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      addToast('error', `Verification failed: ${msg}`);
    }
  };

  return (
    <div className="app-root">
      <Header apiConnected={isApiConnected} isSimulated={isFallback} />

      {/* Page intro */}
      <section className="monitor-intro" aria-label="Page introduction">
        <div className="monitor-intro-inner">
          <h1 className="monitor-title">Satellite monitoring</h1>
          <p className="monitor-subtitle">
            Explore Sentinel-2 observations of Lake Victoria and see where our system has identified
            possible floating vegetation. Each result includes information about the image, the
            analysis, and how certain the system is about what it found.
          </p>
          <div className="monitor-area-pill">
            <span className="monitor-area-dot" aria-hidden="true" />
            Study area: Dunga Beach, Winam Gulf, Kenya
            <span className="monitor-area-sep" aria-hidden="true">·</span>
            10 m per pixel (Sentinel-2)
          </div>
        </div>
      </section>

      <main className="app-layout" id="main-content">
        <section aria-label="Observation overview">
          {error && (
            <div
              style={{
                background: 'rgba(255, 107, 107, 0.1)',
                border: '1px solid rgba(255, 107, 107, 0.3)',
                borderRadius: 'var(--radius)',
                padding: '12px 18px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                color: 'var(--text)',
                fontSize: '0.82rem',
              }}
              role="alert"
            >
              <div>
                <span style={{ marginRight: '8px' }}>⚠️</span>
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={() => refetch()}
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  padding: '4px 12px',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  fontSize: '0.78rem',
                }}
              >
                Retry connection
              </button>
            </div>
          )}

          <StatsRow hotspots={hotspots} isSampleData={isFallback} />

          {isFallback && (
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                borderRadius: 'var(--radius)',
                padding: '10px 16px',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                color: '#fbbf24',
                fontSize: '0.8rem',
              }}
            >
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
              <span>
                The live API backend is offline. These are reference fixture observations, not current
                satellite data.
              </span>
            </div>
          )}

          <AreaOverTimeChart
            hotspots={hotspots}
            selectedDate={selectedDate}
            onSelectDate={(d) => setSelectedDate(d)}
            isSampleData={isFallback}
          />

          <HotspotList
            hotspots={hotspots}
            selectedDate={selectedDate}
            onSelect={(date) => setSelectedDate(date)}
            isLoading={isLoading}
            isSampleData={isFallback}
          />

          {/* Limitations notice */}
          <div className="monitor-limitations" role="note" aria-label="Important limitations">
            <div className="limitations-header">
              <span className="limitations-icon" aria-hidden="true">ℹ</span>
              <strong>What satellite observations cannot tell us</strong>
            </div>
            <ul className="limitations-list">
              <li>
                <strong>Clouds and poor image quality</strong> can prevent the system from seeing anything, a failed or inconclusive result does not mean the area is clear.
              </li>
              <li>
                <strong>The system identifies patterns</strong>, not plant species. Shoreline vegetation, shallow sediment, and other features can produce similar spectral signatures to floating vegetation.
              </li>
              <li>
                <strong>Each image describes conditions at its acquisition time.</strong> Floating vegetation can shift with wind and current, so a clear observation on one date does not mean other areas are clear.
              </li>
              <li>
                <strong>Tracking movement</strong> requires observations across multiple dates and additional evidence, a single image cannot establish direction or predict future position.
              </li>
              <li>
                <strong>Human review and field observation</strong> remain important for assessing candidate findings before acting on them.
              </li>
              <li>
                <strong>A candidate patch is not confirmation of water hyacinth.</strong> It is an area the system has flagged for further investigation.
              </li>
            </ul>
          </div>
        </section>

        <HotspotDetail
          hotspot={selectedHotspot}
          onClose={() => setSelectedDate(null)}
          onVerify={handleVerify}
          isVerifying={isVerifying}
          isSampleData={isFallback}
          onInspect={handleInspect}
          isInspecting={isInspecting}
          inspectError={inspectError}
          traces={traces}
        />
      </main>

      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
