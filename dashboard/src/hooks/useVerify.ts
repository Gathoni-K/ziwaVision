import { useState, useCallback } from 'react';
import { Hotspot, VerificationStatus } from '../types/hotspot';
import { verifyHotspot } from '../api/client';

export interface UseVerifyResult {
  isVerifying: boolean;
  verify: (
    hotspot: Hotspot,
    newStatus: VerificationStatus,
    isFallback?: boolean
  ) => Promise<Hotspot>;
}

export function useVerify(): UseVerifyResult {
  const [isVerifying, setIsVerifying] = useState(false);

  const verify = useCallback(
    async (
      hotspot: Hotspot,
      newStatus: VerificationStatus,
      isFallback = false
    ): Promise<Hotspot> => {
      setIsVerifying(true);
      try {
        if (isFallback) {
          // If in offline fixture mode, simulate local state update
          await new Promise((resolve) => setTimeout(resolve, 400));
          const updated: Hotspot = {
            ...hotspot,
            verification_status: newStatus,
            verified_at: new Date().toISOString(),
          };
          return updated;
        }

        const res = await verifyHotspot({
          date: hotspot.date,
          verified: newStatus === 'verified',
          status: newStatus,
        });

        if (res.ok && res.updated) {
          return res.updated;
        }

        // Fallback local update if updated object wasn't in response
        return {
          ...hotspot,
          verification_status: newStatus,
          verified_at: new Date().toISOString(),
        };
      } finally {
        setIsVerifying(false);
      }
    },
    []
  );

  return { isVerifying, verify };
}
