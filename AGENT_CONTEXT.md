## SCOPE UPDATE (overrides everything below it)

We are building a focused MVP: VISUAL HOTSPOT VERIFICATION.
1. Input: dated Sentinel-2 L2A imagery of selected Lake Victoria locations.
2. Detect: OpenCV 5 segments candidate floating vegetation and estimates patch extent (ha).
3. Assess: evaluate image quality and detection confidence; compare detections against hand-labelled reference imagery.
4. Decide: an agent chooses the next step per hotspot: process_another_observation, request_human_verification, or flag_uncertain.
5. Deliver: an AWS-hosted interface shows candidate hotspots, observation dates, estimated patch areas and verification status.

SENSORS: Sentinel-2 optical and Sentinel-1 radar (VV, VH) are both used. We do NOT fuse pixels. Each produces candidate patches; the agent compares them (overlap, area, position) and acts on agreement or disagreement.
Radar is a core tool (analyze_radar), but its data access, calibration and thresholds are UNVERIFIED until the radar access check and the radar look have been run and reviewed. Treat "VH responds to vegetation, VV to wind roughness" as a hypothesis to test, not a rule. Wind-roughened water is a known false-alarm source and must be detected and reported.
Never claim "hyacinth" before human verification. Radar and optical agreement is evidence, not proof.

## ACTIVE INSPECTOR (agent design)
ZiwaVision Active Inspector investigates suspected hotspots instead of accepting the first detection.
Loop: (1) receive image and metadata; (2) OpenCV analyses it: candidate mask, coverage, quality checks; (3) the agent selects the next step from a fixed tool menu: accept for review, inspect a crop, try an alternative analysis, check persistence against the previous clear date, fetch another scene, or request human verification; (4) execute the tool, reassess, and log evidence, decision, outcome and any human approval.
Rule: every decision must be justified by actual OpenCV output (numbers in the trace). Basic gates (quality, confidence, area, agreement between analyses) are deterministic and testable. An LLM may orchestrate only if it is constrained to the tool menu and the deterministic gates still apply.
We do NOT claim to predict hyacinth movement.

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
- Reflectance offset: resolved (`earthsearch:boa_offset_applied` is True; 2026-08-28 lake pixels: red min=309, median=666, max=2737; NIR min=139, median=325, max=4109 — normal 0 to 10,000 reflectance, no +1000 offset to remove)

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

---

## Current status (updated 2026-10-26)

### Module completion

| File | Status | Notes |
|---|---|---|
| `src/pipeline.py` | ✅ Done | Searches STAC, reads bands, SCL, lake mask, shore ring; reflectance offset confirmed resolved |
| `src/vision.py` | ✅ Done + guard added | OpenCV 5 segmentation → Patch objects; area-anomaly guard added (warns if candidates >20% of lake) |
| `src/reference.py` | ✅ Done | IoU vs reference mask; `build_reference_mask`, `save_reference_labels` |
| `src/assess.py` | ✅ Done | Combines SceneVision + reference IoU → SceneAssessment |
| `src/agent.py` | ✅ Done | Stateless rule agent; 3 actions; `apply_verification` for human override |
| `src/run_pipeline.py` | ✅ Done | Full orchestration loop; writes results.json, decisions.jsonl, overlays |
| `src/api.py` | ✅ Done + S3 added | Flask REST; S3-backed load/save added (falls back to local file for dev) |
| `dashboard/` | ✅ Done | Vite + React + TypeScript; dark-mode; fixture fallback; verify controls |
| `deploy/template.yaml` | ✅ Done | SAM: Lambda + API Gateway + S3 bucket + IAM role |
| `deploy/deploy.sh` | ✅ Fixed | Added `npm run build` + syncs `dashboard/dist/`; removed stale `app.js` patch |

### Known issues observed

- **Anomalous detections (2026-07-04, 2026-07-06):** `decisions.jsonl` shows `total_area_ha` of 1751 ha and 2452 ha — nearly half the 4610 ha lake. Root cause: the reference lake mask was not yet built when those scenes ran (reference is from Aug-28), so `scene_iou=0.0` and the agent correctly chose `process_another_observation`. The area-anomaly guard added to `vision.py` will now print a warning and annotate the patches.
- **`explore_tile.py`** is not touched per project rules; it is an exploration script only.

### Language rule compliance

- All code added in this session uses "candidate floating vegetation" throughout.
- `results.json` agent_reason for 2026-09-07 reads "candidate floating vegetation confirmed consistent with reference" ✓.

### What remains (MVP)

- Run `python src/run_pipeline.py` end-to-end on fresh credentials to regenerate `results.json` with the anomaly guard active.
- Set `BUCKET=<your-unique-name>` and run `bash deploy/deploy.sh` to push to AWS.
- Optionally set `VITE_API_BASE_URL` in `dashboard/.env.production` if not using the deploy script.
- Graviton benchmark: change `Architectures: [x86_64]` → `[arm64]` in `deploy/template.yaml` and re-deploy (last, optional).
