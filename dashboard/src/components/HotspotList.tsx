import React, { useState, useMemo } from 'react';
import { Hotspot } from '../types/hotspot';
import { HotspotCard } from './HotspotCard';

interface HotspotListProps {
  hotspots: Hotspot[];
  selectedDate: string | null;
  onSelect: (date: string) => void;
  isLoading?: boolean;
  isSampleData?: boolean;
}

type SortKey =
  | 'date'
  | 'location'
  | 'n_patches'
  | 'total_area_ha'
  | 'image_quality'
  | 'mean_patch_confidence'
  | 'action'
  | 'verification_status';

export const HotspotList: React.FC<HotspotListProps> = ({
  hotspots,
  selectedDate,
  onSelect,
  isLoading = false,
  isSampleData = false,
}) => {
  const [filterQuery, setFilterQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<-1 | 1>(-1); // -1 = desc, 1 = asc

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(-1);
    }
  };

  const filteredAndSorted = useMemo(() => {
    let list = [...hotspots];

    if (filterQuery.trim()) {
      const q = filterQuery.toLowerCase();
      list = list.filter(
        (h) =>
          h.date.toLowerCase().includes(q) ||
          h.location.toLowerCase().includes(q) ||
          h.verification_status.toLowerCase().includes(q) ||
          h.action.toLowerCase().includes(q)
      );
    }

    list.sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortDir * valA.localeCompare(valB);
      }
      return sortDir * (((valA as number) || 0) - ((valB as number) || 0));
    });

    return list;
  }, [hotspots, filterQuery, sortKey, sortDir]);

  const renderSortIcon = (key: SortKey) => {
    if (sortKey !== key) return <span className="sort-icon">↕</span>;
    return <span className="sort-icon">{sortDir === 1 ? '↑' : '↓'}</span>;
  };

  return (
    <div className="table-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <h2>Observation Log</h2>
          {isSampleData && (
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
          )}
        </div>
        <span className="count-badge">
          {filteredAndSorted.length} scene{filteredAndSorted.length !== 1 ? 's' : ''}
        </span>
        <div className="spacer" />
        <input
          type="search"
          className="filter-input"
          placeholder="Filter by date or status…"
          value={filterQuery}
          onChange={(e) => setFilterQuery(e.target.value)}
          aria-label="Filter hotspots"
        />
      </div>

      <div className="table-wrap" role="region" aria-label="Hotspot table">
        {isLoading ? (
          <div className="loading-state">
            <div className="spinner" role="status" aria-label="Loading observations" />
            <p>Fetching candidate vegetation observations…</p>
          </div>
        ) : filteredAndSorted.length === 0 ? (
          <div className="no-results">No candidate observations match your filter.</div>
        ) : (
          <table role="grid" aria-label="Hotspot observation log">
            <thead>
              <tr role="row">
                <th
                  onClick={() => handleSort('date')}
                  className={sortKey === 'date' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('date')}
                  role="columnheader"
                  aria-sort={
                    sortKey === 'date'
                      ? sortDir === 1
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                >
                  Date {renderSortIcon('date')}
                </th>
                <th
                  onClick={() => handleSort('location')}
                  className={sortKey === 'location' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('location')}
                  role="columnheader"
                >
                  Location {renderSortIcon('location')}
                </th>
                <th
                  onClick={() => handleSort('n_patches')}
                  className={sortKey === 'n_patches' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('n_patches')}
                  role="columnheader"
                >
                  Patches {renderSortIcon('n_patches')}
                </th>
                <th
                  onClick={() => handleSort('total_area_ha')}
                  className={sortKey === 'total_area_ha' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('total_area_ha')}
                  role="columnheader"
                >
                  Area (ha) {renderSortIcon('total_area_ha')}
                </th>
                <th
                  onClick={() => handleSort('image_quality')}
                  className={sortKey === 'image_quality' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('image_quality')}
                  role="columnheader"
                >
                  Quality {renderSortIcon('image_quality')}
                </th>
                <th
                  onClick={() => handleSort('mean_patch_confidence')}
                  className={sortKey === 'mean_patch_confidence' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('mean_patch_confidence')}
                  role="columnheader"
                >
                  Confidence {renderSortIcon('mean_patch_confidence')}
                </th>
                <th
                  onClick={() => handleSort('action')}
                  className={sortKey === 'action' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('action')}
                  role="columnheader"
                >
                  Decision {renderSortIcon('action')}
                </th>
                <th
                  onClick={() => handleSort('verification_status')}
                  className={sortKey === 'verification_status' ? 'sorted' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && handleSort('verification_status')}
                  role="columnheader"
                >
                  Status {renderSortIcon('verification_status')}
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSorted.map((hotspot, idx) => (
                <HotspotCard
                  key={hotspot.date}
                  hotspot={hotspot}
                  isSelected={hotspot.date === selectedDate}
                  onSelect={onSelect}
                  index={idx}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
