import React, { useState, useEffect } from 'react';
import { useHotspots } from './hooks/useHotspots';
import { Header } from './components/Header';
import { StatsRow } from './components/StatsRow';
import { AreaOverTimeChart } from './components/AreaOverTimeChart';
import { HotspotList } from './components/HotspotList';
import { HotspotDetail } from './components/HotspotDetail';

export const App: React.FC = () => {
  const {
    hotspots,
    isLoading,
    error,
    isApiConnected,
    isFallback,
    refetch,
  } = useHotspots();

  const [selectedDate, setSelectedDate] = useState<string | null>(null);

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

          <StatsRow hotspots={hotspots} />

          <AreaOverTimeChart
            hotspots={hotspots}
            selectedDate={selectedDate}
            onSelectDate={(d) => setSelectedDate(d)}
          />

          <HotspotList
            hotspots={hotspots}
            selectedDate={selectedDate}
            onSelect={(date) => setSelectedDate(date)}
            isLoading={isLoading}
          />
        </section>

        <HotspotDetail
          hotspot={selectedHotspot}
          onClose={() => setSelectedDate(null)}
        />
      </main>
    </div>
  );
};
