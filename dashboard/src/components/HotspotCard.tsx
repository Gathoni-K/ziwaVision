import React from 'react';
import { Hotspot, AgentAction } from '../types/hotspot';
import { StatusBadge } from './StatusBadge';

interface HotspotCardProps {
  hotspot: Hotspot;
  isSelected: boolean;
  onSelect: (date: string) => void;
  index: number;
}

const ACTION_SHORT: Record<AgentAction, string> = {
  request_human_verification: 'Review →',
  process_another_observation: 'Retry',
  flag_uncertain: 'Uncertain',
};

export const HotspotCard: React.FC<HotspotCardProps> = ({
  hotspot,
  isSelected,
  onSelect,
  index,
}) => {
  const qualityPct = Math.round((hotspot.image_quality || 0) * 100);
  const confPct = Math.round((hotspot.mean_patch_confidence || 0) * 100);
  const actionLabel = ACTION_SHORT[hotspot.action] || hotspot.action;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(hotspot.date);
    }
  };

  return (
    <tr
      className={isSelected ? 'selected' : ''}
      onClick={() => onSelect(hotspot.date)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="row"
      aria-selected={isSelected}
      style={{ animationDelay: `${index * 0.03}s` }}
    >
      <td className="td-date">{hotspot.date}</td>
      <td className="td-location" title={hotspot.location}>
        {hotspot.location}
      </td>
      <td className="td-patches">{hotspot.n_patches}</td>
      <td className="td-area">{hotspot.total_area_ha.toFixed(2)} ha</td>
      <td>
        <div className="td-bar-wrap">
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${qualityPct}%` }} />
          </div>
          <span className="bar-val">{qualityPct}%</span>
        </div>
      </td>
      <td>
        <div className="td-bar-wrap">
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${confPct}%` }} />
          </div>
          <span className="bar-val">{confPct}%</span>
        </div>
      </td>
      <td>
        <span className="action-badge">{actionLabel}</span>
      </td>
      <td>
        <StatusBadge status={hotspot.verification_status} />
      </td>
    </tr>
  );
};
