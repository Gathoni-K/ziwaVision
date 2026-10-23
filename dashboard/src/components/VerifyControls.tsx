import React from 'react';
import { VerificationStatus } from '../types/hotspot';

interface VerifyControlsProps {
  currentStatus: VerificationStatus;
  date: string;
  isVerifying: boolean;
  onVerify: (status: VerificationStatus) => void;
}

export const VerifyControls: React.FC<VerifyControlsProps> = ({
  currentStatus,
  date,
  isVerifying,
  onVerify,
}) => {
  const isVerified = currentStatus === 'verified';
  const isUncertain = currentStatus === 'uncertain';
  const isRejected = currentStatus === 'rejected';

  return (
    <div
      className="detail-actions"
      role="group"
      aria-label="Human verification decision controls"
    >
      <button
        type="button"
        className="btn-action btn-verify"
        disabled={isVerifying || isVerified}
        onClick={() => onVerify('verified')}
        aria-label={`Mark candidate vegetation detections as verified for ${date}`}
      >
        {isVerifying && isVerified ? (
          <span>Saving…</span>
        ) : isVerified ? (
          '✓ Verified'
        ) : (
          '✓ Mark Verified'
        )}
      </button>

      <button
        type="button"
        className="btn-action btn-uncertain"
        disabled={isVerifying || isUncertain}
        onClick={() => onVerify('uncertain')}
        aria-label={`Flag candidate vegetation detections as uncertain for ${date}`}
      >
        {isUncertain ? '⚑ Uncertain' : '⚑ Flag Uncertain'}
      </button>

      <button
        type="button"
        className="btn-action btn-reject"
        disabled={isVerifying || isRejected}
        onClick={() => onVerify('rejected')}
        aria-label={`Reject candidate vegetation detections for ${date}`}
      >
        {isRejected ? '✕ Rejected' : '✕ Reject'}
      </button>
    </div>
  );
};
