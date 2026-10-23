# ZiwaVision

**Autonomous Visual Hotspot Verification for Lake Victoria**

Entry for the **OpenCV AI Competition 2026, powered by AWS**  
**Focus tracks:** *Agentic Vision with OpenCV 5* · *Best Use of COOL (AWS Graviton)*  
**Parent initiative:** **ZiwaClear** — a climate-smart biomass marketplace transforming invasive water hyacinth into clean bio-products.

---

## The Problem

Water hyacinth (*Pontederia crassipes*) is an aggressive invasive weed that infests Lake Victoria, choking waterways, trapping fishing fleets, disrupting transport, and suffocating aquatic ecosystems. 

Through **ZiwaClear**, local harvesters collect floating hyacinth and sell it to processing hubs for conversion into bio-fertilizer, clean biogas, and artisanal goods. ZiwaClear manages worker payouts and logistics via SMS/USSD and M-Pesa.

### The Operational Bottleneck: Blind Dispatch
Harvesters face a critical limitation: **nobody knows where the weed mats will be tomorrow, or even today**. Wind and lake currents drift massive mats across the gulf overnight. Harvesters waste valuable fuel, physical labor, and daylight scouting blind across open water.

Direct satellite monitoring is also challenging:
- **Cloud cover & haze:** Equatorial lakes experience frequent cloud cover and localized atmospheric interference.
- **Complex coastlines:** Shoreline vegetation, papyrus swamps, and algae blooms often trigger false alarms on simple vegetation index maps.
- **Verification gap:** Sending a commercial harvesting boat based on an unverified satellite pixel blip is costly.

An autonomous system is required to continuously ingest satellite imagery, isolate candidate vegetation within lake water bodies, score image quality and detection confidence, and decide intelligently whether to trigger human verification before dispatching harvesters.

---

## How ZiwaVision Solves It (MVP Scope)

ZiwaVision implements a 5-stage **Visual Hotspot Verification** pipeline powered by OpenCV 5 and an agentic decision engine:

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  1. INGESTION   │       │   2. DETECTION  │       │  3. ASSESSMENT  │
│  Sentinel-2 L2A │ ────► │  OpenCV 5 GrabCut│ ────► │ Quality, Conf., │
│  (AWS STAC API) │       │  & Patch Extent │       │ & IoU vs Ref    │
└─────────────────┘       └─────────────────┘       └─────────────────┘
                                                             │
                                                             ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  5. DELIVERY    │       │ 4b. OPERATOR    │       │   4. DECISION   │
│  AWS Dashboard  │ ◄──── │  VERIFICATION   │ ◄──── │  Vision Agent   │
│  & REST API     │       │  (/api/verify)  │       │  (Audit Log)    │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

### 1. Ingest (Observation Ingestion)
- Searches the open Copernicus Sentinel-2 L2A archive on AWS via Element84 Earth Search STAC API (free, public).
- Extracts 10 m resolution spectral bands (B02 Blue, B03 Green, B04 Red, B08 NIR) alongside the 20 m Scene Classification Layer (SCL) over designated lake sectors.
- Evaluates box-level cloud cover and no-data coverage before downloading full bands.

### 2. Detect (OpenCV 5 Segmentation & Extent Calculation)
- Calculates Normalized Difference Vegetation Index:
  $$\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$$
- Constrains analysis strictly to lake water surfaces using a multi-date consensus water mask (~4,610 ha at the Dunga Beach test site), ignoring land, agricultural crops, and permanent wetlands.
- Uses **OpenCV 5 GrabCut** segmentation seeded by high-NDVI cores to cleanly separate floating plant boundaries from open water and water-shore transition zones.
- Computes connected components to isolate discrete patches, extracting centroid coordinates and area in hectares ($1 \text{ px at } 10\text{ m} = 0.01\text{ ha}$).
- *Scientific rigor:* All unconfirmed detections are formally categorized as **candidate floating vegetation** until human-verified.

### 3. Assess (Quality & Confidence Scoring)
- **Image Quality Score ($Q \in [0, 1]$):** Assesses scene clarity based on localized cloud and no-data pixel fractions.
- **Detection Confidence ($C \in [0, 1]$):** Evaluates vegetation spectral contrast, patch compactness, and GrabCut boundary stability.
- **Reference Intersection-over-Union (IoU):** Compares segmented patches spatially against a vetted clear-sky baseline scene (2026-08-28) to measure persistence and drift.

### 4. Decide (Agentic Vision Loop)
A deterministic vision agent evaluates the assessment metrics and decides the next action per hotspot:
- `image_quality < 0.70` $\rightarrow$ **`process_another_observation`** (requests fallback to alternate observation dates due to cloud/atmospheric degradation).
- `confidence < 0.30` $\rightarrow$ **`flag_uncertain`** (prevents false alarms from sun glint, turbidity, or ephemeral algae).
- `confidence >= 0.55` AND `IoU >= 0.05` AND $\text{area} \ge 0.05\text{ ha}$ $\rightarrow$ **`request_human_verification`** (flags high-probability candidate hotspot for operator review).
- Every decision is written to an append-only JSONL audit log (`outputs/decisions.jsonl`) capturing reasoning and timestamps.

### 5. Deliver (AWS Web Interface & REST API)
- **Flask REST API (`src/api.py`):** Serves hotspot records, patch metadata, and side-by-side true-colour / segmentation overlay images. Includes AWS Lambda serverless handler (`Mangum`).
- **Verification Dashboard (`dashboard/`):** A modern, dark-mode web application showing hotspot coordinates, observation dates, estimated patch areas (ha), and confidence scores.
- **Operator-in-the-Loop:** Allows an operator to review satellite overlays and formally verify or reject candidate detections with a single click.

---

## Test Site & Key Metrics

| Metric | Value |
|---|---|
| **Primary Test Sector** | Dunga Beach, Winam Gulf, Lake Victoria |
| **Bounding Box** | `[34.73, -0.22, 34.83, -0.12]` (W, S, E, N, EPSG:4326) |
| **Pixel Resolution** | 10 m ($1 \text{ pixel} = 0.01 \text{ ha}$) |
| **Reference Lake Area** | ~4,610 ha (consensus across clear scenes) |
| **Reference Scene Date** | 2026-08-28 (0.0% cloud cover, 100% lake coverage) |
| **Clear Scenes Available** | 9 of 11 dates in Jul–Sep 2026 (box cloud $< 5\%$) |
| **Shore Buffer Zone** | ~4,536 ha (3 px inside / 5 px outside lake edge) |

---

## System Architecture

```
ZiwaVision/
├── AGENT_CONTEXT.md       # Target MVP specification & operational rules
├── Readme.md              # Project overview and documentation
├── requirements.txt       # Python dependencies
├── dashboard/             # Static verification dashboard (S3-hosted)
│   ├── index.html         # Responsive dark-mode interface
│   ├── app.js             # API client, table renderer, overlay viewer
│   ├── style.css          # Modern typography, gradients, glassmorphism
│   └── logo.jpg           # ZiwaVision branding
├── deploy/                # AWS Infrastructure as Code
│   ├── template.yaml      # AWS SAM template (S3, API Gateway, Lambda)
│   └── deploy.sh          # One-click deployment script
├── outputs/               # Generated run outputs (git-ignored)
│   ├── results.json       # Processed hotspots, metrics, and agent decisions
│   ├── decisions.jsonl    # Immutable audit trail of agent actions
│   ├── reference_labels.json # Baseline patches from 2026-08-28
│   └── overlays/          # Generated side-by-side verification PNGs
└── src/                   # Core Python modules
    ├── pipeline.py        # STAC query, band windowing, SCL lake mask
    ├── vision.py          # OpenCV 5 GrabCut segmentation & patch extraction
    ├── reference.py       # Reference baseline generator & IoU calculator
    ├── assess.py          # Image quality & detection confidence scorers
    ├── agent.py           # Agentic decision engine & audit logger
    ├── run_pipeline.py    # Multi-scene orchestrator
    └── api.py             # Flask & Mangum REST API server
```

---

## Status

| Component | MVP Status | Description |
|---|---|---|
| **Sentinel-2 Search & Ingestion** | ✅ Complete | STAC catalog integration via Element84 on AWS |
| **Consensus Lake Masking** | ✅ Complete | Multi-date SCL water aggregation |
| **OpenCV 5 Segmentation** | ✅ Complete | NDVI thresholding + GrabCut edge refinement |
| **Patch Area & Centroids** | ✅ Complete | Extent measured in hectares (10 m pixel scale) |
| **Quality & Confidence Scoring** | ✅ Complete | Multi-factor image quality and patch confidence |
| **Reference IoU Comparison** | ✅ Complete | Automatic spatial comparison against 2026-08-28 baseline |
| **Agent Decision Engine** | ✅ Complete | Deterministic routing with immutable audit log |
| **Verification REST API** | ✅ Complete | Flask endpoints + Lambda Mangum handler |
| **Interactive Dashboard** | ✅ Complete | Dark-mode web interface with image overlays |
| **AWS SAM Cloud Deployment** | ✅ Complete | S3 static site + API Gateway + Lambda template |
| **Multi-date Batch Run** | 🔄 Running | Processing 14 scenes from Q3 2026 |
| **Graviton (COOL) Benchmark** | 📋 Future | Latency & cost comparison (arm64 vs x86_64) |
| **Radar / Climate Fusion** | 📋 Future | Out of MVP scope (see Future Work) |

---

## Getting Started

### Prerequisites
- Python 3.12+
- GDAL / PROJ compatible environment
- (Optional) AWS CLI configured if deploying to AWS

### 1. Installation

```bash
git clone https://github.com/Gathoni-K/ziwaVision.git
cd ziwaVision

python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\Activate.ps1

pip install -r requirements.txt
mkdir -p outputs/overlays
```

*Note: Access to the Element84 Earth Search Sentinel-2 STAC catalog is public and requires no API keys.*

### 2. Run the Verification Pipeline

To process historical Sentinel-2 acquisitions, segment candidate floating vegetation, calculate quality scores, and run agent decisions:

```bash
python src/run_pipeline.py
```

This generates:
- `outputs/results.json`: Complete structured detection summary.
- `outputs/decisions.jsonl`: Audit log of agent decisions.
- `outputs/reference_labels.json`: Baseline patches from the reference date.
- `outputs/overlays/<date>.png`: Side-by-side RGB true-colour and segmentation overlays.

### 3. Launch the Local Dashboard & API

Start the backend API server:

```bash
python src/api.py
```
*API runs on `http://127.0.0.1:5000`.*

Open `dashboard/index.html` in your web browser. The dashboard connects to the local API, displays hotspot cards, renders side-by-side satellite overlays, and lets you verify candidate detections.

### 4. Deploy to AWS

Deploy the static dashboard to Amazon S3 and the API to AWS Lambda / API Gateway using AWS SAM:

```bash
export BUCKET=ziwavision-dashboard-2026
bash deploy/deploy.sh
```

To run on **AWS Graviton (arm64)**, update `Architectures: [arm64]` under `Globals.Function` in `deploy/template.yaml`.

---

## Limitations & Edge Cases

1. **Spatial Resolution (10 m):** Small weed patches under 10 m across are sub-pixel and may blend into surrounding water reflectance.
2. **Spectral Ambiguity:** High NDVI identifies healthy photosynthetic vegetation. Near shorelines, dense algae blooms or emergent reeds (papyrus) can mimic floating mats. GrabCut and lake masking minimize this, but human verification remains essential before physical dispatch.
3. **Cloud Gaps:** Persistent cloud cover over equatorial lakes can cause data gaps between usable optical passes (Sentinel-2 revisit is every 5 days).
4. **Tile Boundary Coverage:** Dunga Beach sits near the boundary between Sentinel-2 tiles (`36MXE` covers the full area; `36MYE` provides only partial coverage). The ingestion pipeline explicitly validates spatial coverage before processing.

---

## Future Improvements

While the current MVP delivers an end-to-end Visual Hotspot Verification pipeline, several architectural enhancements are planned:

- **Sentinel-1 SAR Radar Fusion:** Integrate C-band Synthetic Aperture Radar (SAR) from Sentinel-1. Radar pulses penetrate cloud cover and rain, enabling continuous day/night tracking during peak rainy seasons when optical Sentinel-2 imagery is obscured.
- **Climate-Driven Risk & Runoff Scoring (`acmadDL`):** Ingest rainfall and temperature forecasts to model agricultural runoff and nutrient influx into Winam Gulf, predicting high-risk conditions that precede rapid hyacinth reproduction.
- **Biomass Density & Tonnage Estimation:** Combine optical reflectance depth with ground-truth harvester weight logs to convert patch area (ha) into estimated wet/dry biomass tonnage, assisting commercial bio-refineries in production planning.
- **Automated Fleet Dispatch Integration:** Connect verified hotspots directly to ZiwaClear's SMS/USSD dispatch engine to send SMS alert broadcasts to registered boat cooperatives with coordinates and navigation bearings.
- **AWS Graviton Benchmarking (COOL Track):** Systematically benchmark OpenCV 5 segmentation execution on AWS Graviton3/4 processors (arm64) versus traditional x86_64 architectures to demonstrate cost, compute latency, and carbon emission reductions for humanitarian environmental workflows.

---

## Credits & Data Sources

- **Imagery:** Copernicus Sentinel-2 L2A, hosted as open public data on AWS by Element84 Earth Search.
- **Computer Vision:** OpenCV 5 (GrabCut, morphology, contour analysis, connected components).
- **Cloud Infrastructure:** AWS Lambda, Amazon API Gateway, Amazon S3, AWS SAM, AWS Graviton.
- **Initiative:** Developed in support of the **ZiwaClear** biomass marketplace for Lake Victoria.
- **Competition:** Entry for the **OpenCV AI Competition 2026, powered by AWS**.