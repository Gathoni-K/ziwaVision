import React from 'react';
import { VerificationStatus } from '../types/hotspot';

interface StatusBadgeProps {
  status: VerificationStatus;
}

const STATUS_CONFIG: Record<VerificationStatus, { label: string; icon: string; className: string }> = {
  needs_review: {
    label: 'Needs Review',
    icon: '⏳',
    className: 'badge-needs_review',
  },
  needs_verification: {
    label: 'Needs Verification',
    icon: '⏳',
    className: 'badge-needs_review',
  },
  candidate: {
    label: 'Candidate',
    icon: '🔍',
    className: 'badge-uncertain',
  },
  verified: {
    label: 'Verified',
    icon: '✓',
    className: 'badge-verified',
  },
  uncertain: {
    label: 'Uncertain',
    icon: '⚑',
    className: 'badge-uncertain',
  },
  rejected: {
    label: 'Rejected',
    icon: '✕',
    className: 'badge-rejected',
  },
  rejected_as_artefact: {
    label: 'Artefact',
    icon: '✕',
    className: 'badge-rejected',
  },
  skipped: {
    label: 'Skipped',
    icon: '—',
    className: 'badge-skipped',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config = STATUS_CONFIG[status] || {
    label: status,
    icon: '•',
    className: 'badge-skipped',
  };

  return (
    <span
      className={`badge ${config.className}`}
      role="status"
      aria-label={`Status: ${config.label}`}
      title={`Verification status: ${config.label}`}
    >
      <span className="badge-dot" aria-hidden="true" />
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
};
