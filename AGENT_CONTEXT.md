## SCOPE UPDATE (overrides everything below it)

We are building a focused MVP: VISUAL HOTSPOT VERIFICATION.
1. Input: dated Sentinel-2 L2A imagery of selected Lake Victoria locations.
2. Detect: OpenCV 5 segments candidate floating vegetation and estimates patch extent (ha).
3. Assess: evaluate image quality and detection confidence; compare detections against hand-labelled reference imagery.
4. Decide: an agent chooses the next step per hotspot: process_another_observation, request_human_verification, or flag_uncertain.
5. Deliver: an AWS-hosted interface shows candidate hotspots, observation dates, estimated patch areas and verification status.

OUT OF SCOPE: Sentinel-1 radar and optical/radar fusion, rainfall and wind risk scoring, real-time tracking, biomass or tonnage estimates, forecasting. Ignore the radar, climate and risk-score sections below; they are future work.
Never describe a detection as "hyacinth" before it is verified. Use "candidate floating vegetation".
The Graviton vs x86 benchmark is optional and last.

---

## Project: ZiwaVision — Visual Hotspot Verification (MVP)

**Competition:** OpenCV AI Competition 2026, powered by AWS.
**Focus paths:** Agentic Vision with OpenCV 5 · Best Use of COOL (AWS Graviton, optional).
**Parent initiative:** ZiwaClear — a climate-smart biomass marketplace for Lake Victoria.

### Test site
Dunga Beach, Winam Gulf — bounding box `[34.73, -0.22, 34.83, -0.12]` (W, S, E, N, EPSG:4326).
Reference date: 2026-08-28 (0.0% cloud, 100% reference lake coverage).

### Module map

| File | Role |
|---|---|
| `src/pipeline.py` | Scene search, band reading, SCL, lake mask (existing) |
| `src/vision.py` | OpenCV 5 segmentation → list of Patch objects |
| `src/reference.py` | IoU comparison against reference labels |
| `src/assess.py` | Image quality + detection confidence scorer |
| `src/agent.py` | Stateless rule-based agent, writes decisions.jsonl |
| `src/run_pipeline.py` | Orchestration: loop all dates → results.json |
| `src/api.py` | Flask REST API (hotspots, overlay PNGs, verify endpoint) |
| `dashboard/` | Static dark-mode UI hosted on S3 |
| `deploy/` | AWS SAM template + deploy script |

### Data produced

- `outputs/results.json` — all scene assessments and agent decisions
- `outputs/decisions.jsonl` — one JSON line per scene (append-only log)
- `outputs/reference_labels.json` — reference patches from the Aug-28 scene
- `outputs/overlays/<date>.png` — RGB + candidate overlay for each scene

### Key numbers from existing scripts

- Reference lake area: ~4,610 ha (9-date consensus, min_share=0.6)
- Pixel resolution: 10 m → 1 pixel = 0.01 ha
- Clear scenes (box cloud < 5%): 9 of 11 in Jul–Sep 2026
- Cloud cutoff: 5% (box-level, not tile-level — see run_cloud.py notes)
- Shore band: ~4,536 ha (3 px inside / 5 px outside lake edge)

### Language rules

- Say "candidate floating vegetation", not "hyacinth", until a human marks a detection as verified.
- Detection confidence is a model score (0–1); it is not a claim about the species.
- All area estimates are labelled as estimates and carry the pixel-resolution caveat (10 m).

### What is NOT built in this MVP

- Sentinel-1 radar processing or optical/radar fusion
- Rainfall, wind, or any climate-derived risk score
- Real-time or near-real-time tracking
- Biomass or tonnage estimates
- Any forecasting or predictive model
- Graviton benchmark (optional, do last if time allows)
