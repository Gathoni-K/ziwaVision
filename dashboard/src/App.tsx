import React, { useState, useEffect, useCallback } from 'react';
import { useHotspots } from './hooks/useHotspots';
import { useVerify } from './hooks/useVerify';
import { Header } from './components/Header';
import { StatsRow } from './components/StatsRow';
import { AreaOverTimeChart } from './components/AreaOverTimeChart';
import { HotspotList } from './components/HotspotList';
import { HotspotDetail } from './components/HotspotDetail';
import { Toast, ToastMessage } from './components/Toast';
import { VerificationStatus } from './types/hotspot';

export const App: React.FC = () => {
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

  // Automatically select the first needs_review observation on load (matching old dashboard UX)
  useEffect(() => {
    if (!selectedDate && hotspots.length > 0) {
      const reviewItem = hotspots.find((h) => h.verification_status === 'needs_review');
      if (reviewItem) {
        setSelectedDate(reviewItem.date);
      }
    }
  }, [hotspots, selectedDate]);

  const selectedHotspot =
    hotspots.find((h) => h.date === selectedDate) || null;

  const handleVerify = async (newStatus: VerificationStatus) => {
    if (!selectedHotspot) return;

    try {
      const updated = await verify(selectedHotspot, newStatus, isFallback);
      updateLocalHotspot(updated);

      const statusLabels: Record<VerificationStatus, string> = {
        verified: 'marked as verified ✓',
        uncertain: 'flagged as uncertain ⚑',
        rejected: 'rejected ✕',
        needs_review: 'reset to needs review',
        skipped: 'skipped',
      };

      addToast(
        'success',
        `Scene ${selectedHotspot.date} ${statusLabels[newStatus] || newStatus}.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      addToast('error', `Verification failed: ${msg}`);
    }
  };

  return (
    <div className="app-root">
      <Header apiConnected={isApiConnected} isSimulated={isFallback} />

      <main className="app-layout" id="main-content">
        <section aria-label="Hotspot overview">
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
                Retry Connection
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
                Displaying fixture/mock observations dataset. Backend API is offline or disconnected.
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
        </section>

        <HotspotDetail
          hotspot={selectedHotspot}
          onClose={() => setSelectedDate(null)}
          onVerify={handleVerify}
          isVerifying={isVerifying}
          isSampleData={isFallback}
        />
      </main>

      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
