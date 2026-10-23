import { useState, useEffect, useCallback } from 'react';
import { Hotspot } from '../types/hotspot';
import { fetchHotspots, checkHealth } from '../api/client';
import { FIXTURE_HOTSPOTS } from '../data/fixtures';

export interface UseHotspotsResult {
  hotspots: Hotspot[];
  isLoading: boolean;
  error: string | null;
  isApiConnected: boolean;
  isFallback: boolean;
  refetch: () => Promise<void>;
  updateLocalHotspot: (updated: Hotspot) => void;
}

export function useHotspots(): UseHotspotsResult {
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isApiConnected, setIsApiConnected] = useState<boolean>(false);
  const [isFallback, setIsFallback] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const healthy = await checkHealth();
    setIsApiConnected(healthy);

    if (healthy) {
      try {
        const data = await fetchHotspots();
        setHotspots(data);
        setIsFallback(false);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unknown network error';
        setError(msg);
        // Fallback to fixture data for seamless developer experience
        setHotspots(FIXTURE_HOTSPOTS);
        setIsFallback(true);
      }
    } else {
      setError('Could not connect to ZiwaVision API (offline). Displaying reference fixture dataset.');
      setHotspots(FIXTURE_HOTSPOTS);
      setIsFallback(true);
    }

    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateLocalHotspot = useCallback((updated: Hotspot) => {
    setHotspots((prev) =>
      prev.map((item) => (item.date === updated.date ? updated : item))
    );
  }, []);

  return {
    hotspots,
    isLoading,
    error,
    isApiConnected,
    isFallback,
    refetch: loadData,
    updateLocalHotspot,
  };
}
