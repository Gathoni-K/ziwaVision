import React from 'react';

interface HeaderProps {
  apiConnected: boolean;
  isSimulated?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ apiConnected, isSimulated = false }) => {
  return (
    <header className="header" role="banner">
      <img
        src="/logo.jpg"
        alt="ZiwaVision Logo — Lake Victoria"
        className="header-logo"
      />
      <div className="header-titles">
        <h1>ZiwaVision</h1>
        <p>Visual Hotspot Verification · Lake Victoria</p>
      </div>
      <div className="header-spacer" />
      {isSimulated && (
        <span
          className="sample-data-badge"
          style={{
            background: '#f59e0b',
            color: '#000000',
            fontWeight: 800,
            fontSize: '0.72rem',
            padding: '4px 10px',
            borderRadius: '4px',
            letterSpacing: '0.08em',
            marginRight: '12px',
            boxShadow: '0 0 10px rgba(245, 158, 11, 0.4)',
          }}
        >
          SAMPLE DATA
        </span>
      )}
      <div className="header-pill" aria-live="polite">
        <span
          className={`dot ${apiConnected ? 'connected' : 'offline'}`}
          aria-hidden="true"
        />
        <span>
          {isSimulated
            ? 'Demo Fixture Mode'
            : apiConnected
            ? 'API connected'
            : 'API offline'}
        </span>
      </div>
    </header>
  );
};
