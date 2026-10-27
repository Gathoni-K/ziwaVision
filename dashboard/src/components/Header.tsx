import React from 'react';
import { NavLink } from 'react-router-dom';

interface HeaderProps {
  apiConnected?: boolean;
  isSimulated?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ apiConnected, isSimulated = false }) => {
  return (
    <header className="header" role="banner">
      <NavLink to="/" aria-label="ZiwaVision home" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
        <img
          src="/logo.jpg"
          alt="ZiwaVision — Lake Victoria satellite monitoring"
          className="header-logo"
        />
        <div className="header-titles">
          <div className="header-brand">ZiwaVision</div>
          <p>Lake Victoria · Satellite Monitoring</p>
        </div>
      </NavLink>

      <nav className="header-nav" aria-label="Main navigation">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `header-nav-link${isActive ? ' active' : ''}`}
        >
          Home
        </NavLink>
        <NavLink
          to="/monitor"
          className={({ isActive }) => `header-nav-link${isActive ? ' active' : ''}`}
        >
          Satellite Monitoring
        </NavLink>
      </nav>

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

      {apiConnected !== undefined && (
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
      )}
    </header>
  );
};
