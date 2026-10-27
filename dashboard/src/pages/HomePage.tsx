import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Header } from '../components/Header';
import { fetchHotspots, checkHealth } from '../api/client';
import { Hotspot } from '../types/hotspot';

// Derive a human-readable outcome label for a hotspot
function outcomeLabel(h: Hotspot): string {
  switch (h.verification_status) {
    case 'verified': return 'Verified by a reviewer';
    case 'rejected': return 'Rejected by a reviewer';
    case 'needs_review':
    case 'needs_verification': return 'Pending human review';
    case 'uncertain': return 'Uncertain — inconclusive evidence';
    case 'rejected_as_artefact': return 'Rejected as an analysis artefact';
    case 'candidate': return 'Candidate patch identified';
    case 'skipped': return 'No suitable scene available';
    default: return h.verification_status;
  }
}

export const HomePage: React.FC = () => {
  const [recentHotspots, setRecentHotspots] = useState<Hotspot[]>([]);
  const [apiLive, setApiLive] = useState<boolean | null>(null);

  useEffect(() => {
    checkHealth().then((ok) => {
      setApiLive(ok);
      if (ok) {
        fetchHotspots()
          .then((hs) => {
            // Sort descending by date, take 3 most recent with patches
            const sorted = [...hs].sort((a, b) => b.date.localeCompare(a.date));
            setRecentHotspots(sorted.slice(0, 3));
          })
          .catch(() => setRecentHotspots([]));
      }
    });
  }, []);

  return (
    <div className="app-root home-root">
      <Header />

      {/* ─── HERO ──────────────────────────────────────────────────────── */}
      <section className="hero" aria-label="Mission introduction">
        <div className="hero-image-wrap">
          <img
            src="/lake_victoria_hero.jpg"
            alt="Satellite composite of Lake Victoria showing the lake's deep blue expanse, surrounding land, and pale green vegetation near the Winam Gulf shoreline"
            className="hero-image"
          />
          <div className="hero-image-overlay" aria-hidden="true" />
        </div>

        <div className="hero-content">
          <h1 className="hero-headline">
            A clearer view of water hyacinth<br className="hero-br" /> on Lake Victoria.
          </h1>
          <p className="hero-copy">
            ZiwaVision uses satellite imagery and computer vision to identify possible
            floating-vegetation hotspots, examine uncertain detections, and build toward a
            wider picture of changing conditions across Lake Victoria.
          </p>
          <div className="hero-ctas">
            <Link to="/monitor" className="btn-hero-primary" id="hero-cta-monitor">
              Explore satellite observations
            </Link>
            <a href="#mission" className="btn-hero-secondary" id="hero-cta-mission">
              Our mission
            </a>
          </div>
          <p className="hero-disclaimer">
            The images above are composited illustration assets. Actual Sentinel-2 overlays are
            displayed on the{' '}
            <Link to="/monitor" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
              satellite monitoring page
            </Link>
            .
          </p>
        </div>
      </section>

      {/* ─── PROBLEM ────────────────────────────────────────────────────── */}
      <section className="home-section" id="mission" aria-label="Why monitoring matters">
        <div className="home-section-inner">
          <div className="section-eyebrow">The challenge</div>
          <h2 className="section-heading">Floating vegetation that moves with wind and current</h2>
          <div className="two-col-prose">
            <p>
              Water hyacinth forms dense mats on the surface of Lake Victoria. These mats drift with
              wind and current, which means the problem is not fixed in one place. A shoreline that
              appears relatively clear during one observation may not tell us what is happening
              elsewhere on the lake or at a different time.
            </p>
            <p>
              Regular, geographically distributed observations are needed to build a useful picture
              of where possible infestations are appearing and how conditions at specific locations
              change over time. No single observation can substitute for that broader view, and
              satellite imagery alone cannot identify plant species or confirm the presence of
              hyacinth without human review.
            </p>
          </div>
          <div className="problem-cards">
            <div className="problem-card">
              <div className="problem-icon" aria-hidden="true">🌊</div>
              <h3>Mats move</h3>
              <p>Floating vegetation drifts with wind and surface currents. A location that looks clear at one time may not remain so, and patches may appear where none were previously visible.</p>
            </div>
            <div className="problem-card">
              <div className="problem-icon" aria-hidden="true">☁️</div>
              <h3>Observations are limited</h3>
              <p>Clouds, image quality, and satellite revisit times mean that not every area can be observed on every date. Gaps in the record are real, not evidence of a clear lake.</p>
            </div>
            <div className="problem-card">
              <div className="problem-icon" aria-hidden="true">📍</div>
              <h3>Scale is difficult</h3>
              <p>Lake Victoria covers roughly 68,800 km². Systematic monitoring across its full extent requires tools that can process large areas consistently and flag candidates for human review.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── WHAT WE ARE BUILDING ────────────────────────────────────────── */}
      <section className="home-section home-section-alt" aria-label="Current capabilities">
        <div className="home-section-inner">
          <div className="section-eyebrow">What we are building</div>
          <h2 className="section-heading">Four capabilities, built honestly</h2>
          <p className="section-lead">
            The current prototype is a working research tool, not a deployed monitoring service.
            Each capability below exists in functional code and has been tested locally against
            real Sentinel-2 imagery.
          </p>
          <div className="capability-list">
            <div className="capability-item">
              <div className="capability-num" aria-hidden="true">01</div>
              <div className="capability-body">
                <h3>Seeing possible hotspots from space</h3>
                <p>
                  The prototype retrieves Sentinel-2 satellite imagery through the{' '}
                  <strong>Earth Search</strong> public catalogue and screens each scene for areas
                  where the spectral signature is consistent with floating vegetation. This screening
                  produces a list of candidate patches, not confirmed identifications.
                </p>
                <span className="capability-status capability-status-live">Implemented · Live data</span>
              </div>
            </div>

            <div className="capability-item">
              <div className="capability-num" aria-hidden="true">02</div>
              <div className="capability-body">
                <h3>Examining what the satellite sees</h3>
                <p>
                  <strong>OpenCV 5</strong> analyses each scene to identify candidate patches,
                  estimate their apparent size in hectares, and locate them relative to the open
                  water and shoreline. Size estimates are labelled as estimates and carry the 10 m
                  pixel-resolution caveat.
                </p>
                <span className="capability-status capability-status-live">Implemented · OpenCV 5</span>
              </div>
            </div>

            <div className="capability-item">
              <div className="capability-num" aria-hidden="true">03</div>
              <div className="capability-body">
                <h3>Checking uncertain results</h3>
                <p>
                  The <strong>Active Inspector</strong> evaluates image quality, compares alternative
                  detection runs, investigates candidate areas in more detail, and requests human
                  review when the evidence is inconclusive. It applies deterministic rules — not
                  guesswork — and records every decision and its justification.
                </p>
                <span className="capability-status capability-status-live">Implemented · Deterministic gates</span>
              </div>
            </div>

            <div className="capability-item">
              <div className="capability-num" aria-hidden="true">04</div>
              <div className="capability-body">
                <h3>Keeping the evidence visible</h3>
                <p>
                  Every observation, decision, and outcome is recorded so users can inspect why a
                  candidate was flagged or why the system chose not to flag one. This trace is
                  displayed on the satellite monitoring page alongside each observation.
                </p>
                <span className="capability-status capability-status-live">Implemented · Audit trace</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── WHERE WE ARE TODAY ──────────────────────────────────────────── */}
      <section className="home-section" aria-label="Current progress">
        <div className="home-section-inner">
          <div className="section-eyebrow">Where we are today</div>
          <h2 className="section-heading">Development milestones</h2>
          <p className="section-lead">
            The following represent completed work in the current prototype. These are not projected
            capabilities — they exist in the repository and are demonstrated by the satellite
            monitoring page.
          </p>

          <div className="milestone-grid">
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">🛰️</div>
              <h3>Live Sentinel-2 retrieval</h3>
              <p>The pipeline queries the Earth Search STAC catalogue to find and download actual satellite scenes covering the Winam Gulf study area.</p>
            </div>
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">🔬</div>
              <h3>OpenCV 5 vision pipeline</h3>
              <p>Imagery is processed using OpenCV 5 segmentation to produce candidate patches with estimated areas, confidence scores, and position data.</p>
            </div>
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">🤖</div>
              <h3>Active Inspector</h3>
              <p>A rule-based agent applies quality gates, compares detection methods, and decides whether to request human review, investigate further, or skip the scene.</p>
            </div>
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">📋</div>
              <h3>Audit traces</h3>
              <p>Each inspection step is recorded to a persistent trace. Users can read exactly what the system measured, what rule it applied, and what it decided next.</p>
            </div>
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">🔐</div>
              <h3>Human review controls</h3>
              <p>Authorised reviewers can verify or reject candidate findings through an authenticated endpoint. Automated decisions are kept separate from human ones.</p>
            </div>
            <div className="milestone-card">
              <div className="milestone-icon" aria-hidden="true">⚡</div>
              <h3>Failure handling</h3>
              <p>Network errors, missing imagery, and processing failures are recorded in the trace and surfaced to users rather than silently substituted with fallback data.</p>
            </div>
          </div>

          {/* Live observations from API */}
          {recentHotspots.length > 0 && (
            <div className="recent-obs-section" aria-label="Recent observations from the API">
              <h3 className="recent-obs-heading">Recent observations from the API</h3>
              <p className="recent-obs-note">
                These records are loaded from the live backend and reflect actual stored inspection
                results, not illustrative examples.
              </p>
              <div className="recent-obs-list">
                {recentHotspots.map((h) => (
                  <Link
                    to="/monitor"
                    key={h.date}
                    className="recent-obs-card"
                    aria-label={`View observation for ${h.date}`}
                  >
                    <div className="recent-obs-date">{h.date}</div>
                    <div className="recent-obs-location">{h.location}</div>
                    <div className="recent-obs-details">
                      {h.n_patches > 0 ? (
                        <span className="recent-obs-patches">
                          {h.n_patches} candidate patch{h.n_patches !== 1 ? 'es' : ''}
                          {' · '}~{h.total_area_ha.toFixed(1)} ha estimated
                        </span>
                      ) : (
                        <span className="recent-obs-clear">No candidates identified</span>
                      )}
                    </div>
                    <div className="recent-obs-status">{outcomeLabel(h)}</div>
                    <div className="recent-obs-arrow" aria-hidden="true">→</div>
                  </Link>
                ))}
              </div>
              <Link to="/monitor" className="recent-obs-all-link">
                View all observations →
              </Link>
            </div>
          )}

          {apiLive === false && (
            <div className="recent-obs-offline" role="note">
              <span>The live API is currently offline.</span>{' '}
              <Link to="/monitor" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>
                The satellite monitoring page
              </Link>{' '}
              will show sample reference observations while the backend is unavailable.
            </div>
          )}
        </div>
      </section>

      {/* ─── HOW IT WORKS ────────────────────────────────────────────────── */}
      <section className="home-section home-section-alt" aria-label="How the system works">
        <div className="home-section-inner">
          <div className="section-eyebrow">How it works</div>
          <h2 className="section-heading">Four steps, from satellite to evidence</h2>
          <div className="how-steps">
            <div className="how-step">
              <div className="how-step-num" aria-hidden="true">1</div>
              <h3>Observe</h3>
              <p>Find suitable satellite images covering the selected area. The system checks image quality, cloud cover, and whether the lake surface is visible enough to analyse.</p>
            </div>
            <div className="how-step-connector" aria-hidden="true" />
            <div className="how-step">
              <div className="how-step-num" aria-hidden="true">2</div>
              <h3>Examine</h3>
              <p>Analyse the image to identify areas where the spectral pattern is consistent with floating vegetation. These areas are called candidate patches — not confirmed detections.</p>
            </div>
            <div className="how-step-connector" aria-hidden="true" />
            <div className="how-step">
              <div className="how-step-num" aria-hidden="true">3</div>
              <h3>Check</h3>
              <p>Assess whether the image quality and detection confidence meet the threshold for further consideration. When two detection methods disagree, run additional analysis to compare results.</p>
            </div>
            <div className="how-step-connector" aria-hidden="true" />
            <div className="how-step">
              <div className="how-step-num" aria-hidden="true">4</div>
              <h3>Review</h3>
              <p>Present the evidence for human assessment when the system cannot reach a confident conclusion on its own. Only a human reviewer can verify or reject a candidate finding.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── LONG-TERM VISION ────────────────────────────────────────────── */}
      <section className="home-section vision-section" aria-label="Long-term vision">
        <div className="home-section-inner">
          <div className="section-eyebrow">The larger vision</div>
          <h2 className="section-heading">One lake, three countries</h2>
          <p className="section-lead">
            Water hyacinth does not respect national boundaries. Lake Victoria is shared by Kenya,
            Uganda, and Tanzania. The longer-term goal is to expand beyond the initial Kenyan study
            area toward observations across the full lake — but that work begins with getting the
            prototype right.
          </p>

          <div className="vision-timeline">
            <div className="vision-phase">
              <div className="vision-phase-label">Today</div>
              <div className="vision-phase-content">
                <h3>Prototype development</h3>
                <p>Working on a focused study area around Dunga Beach, Winam Gulf, Kenya. Building and testing the detection pipeline, Active Inspector, and evidence trail with real Sentinel-2 imagery.</p>
                <ul className="vision-phase-list">
                  <li>Live Sentinel-2 retrieval and OpenCV 5 analysis</li>
                  <li>Active Inspector with deterministic decision rules</li>
                  <li>Human verification with authenticated access control</li>
                  <li>Persistent audit traces for every inspection</li>
                </ul>
              </div>
            </div>

            <div className="vision-phase-sep" aria-hidden="true" />

            <div className="vision-phase vision-phase-next">
              <div className="vision-phase-label vision-phase-label-next">Next</div>
              <div className="vision-phase-content">
                <h3>Expanded coverage and reliability</h3>
                <p>Extend observations beyond the current bounding box, improve detection reliability, and build tools to compare how candidate areas change between acquisition dates.</p>
                <ul className="vision-phase-list">
                  <li>Broader geographic coverage within Lake Victoria</li>
                  <li>Multi-date comparison to track changes over time</li>
                  <li>Improved detection thresholds and false-alarm reduction</li>
                  <li>More complete coverage of cloud-affected periods</li>
                </ul>
              </div>
            </div>

            <div className="vision-phase-sep" aria-hidden="true" />

            <div className="vision-phase vision-phase-future">
              <div className="vision-phase-label vision-phase-label-future">Long term</div>
              <div className="vision-phase-content">
                <h3>Lake-wide monitoring</h3>
                <p>Work toward observations across the lake shared by Kenya, Uganda, and Tanzania. Connect satellite observations, verified field reports, and date-to-date comparisons into a more complete cross-border picture.</p>
                <ul className="vision-phase-list">
                  <li>Lake-wide coverage spanning three countries</li>
                  <li>Integration with field observation and ground-truth data</li>
                  <li>Information sharing across national monitoring programmes</li>
                  <li>Open data access for research and policy</li>
                </ul>
                <p className="vision-phase-note">
                  <em>These are stated ambitions, not confirmed partnerships or deployed capabilities.</em>
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── CTA ─────────────────────────────────────────────────────────── */}
      <section className="home-cta-section" aria-label="Explore observations">
        <div className="home-section-inner">
          <h2 className="home-cta-heading">See what the satellite observations reveal.</h2>
          <p className="home-cta-sub">
            Browse actual Sentinel-2 scenes, candidate patches, and the evidence the Active
            Inspector recorded for each one.
          </p>
          <Link to="/monitor" className="btn-hero-primary btn-cta-lg" id="footer-cta-monitor">
            Open satellite monitoring →
          </Link>
        </div>
      </section>

      {/* ─── FOOTER ──────────────────────────────────────────────────────── */}
      <footer className="home-footer" role="contentinfo">
        <div className="home-footer-inner">
          <div className="home-footer-brand">
            <img src="/logo.jpg" alt="" aria-hidden="true" className="footer-logo" />
            <div>
              <div className="footer-brand-name">ZiwaVision</div>
              <div className="footer-brand-sub">Lake Victoria · Satellite Monitoring Prototype</div>
            </div>
          </div>
          <nav className="footer-nav" aria-label="Footer navigation">
            <Link to="/" className="footer-nav-link">Home</Link>
            <Link to="/monitor" className="footer-nav-link">Satellite Monitoring</Link>
          </nav>
          <div className="footer-note">
            Part of the <strong>ZiwaClear</strong> initiative.
            Built for the OpenCV AI Competition 2026.
            Imagery: Sentinel-2 L2A via Element84 Earth Search.
          </div>
        </div>
      </footer>
    </div>
  );
};
