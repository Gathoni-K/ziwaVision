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
