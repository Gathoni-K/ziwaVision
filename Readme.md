# ZiwaVision

Predictive, vision-driven early warning and dispatch for water hyacinth on Lake Victoria.

Entry for the **OpenCV AI Competition 2026, powered by AWS**
Focus paths: *Agentic Vision with OpenCV 5* and *Best Use of COOL (AWS Graviton)*.
Parent initiative: **ZiwaClear**, a climate-smart biomass marketplace for Lake Victoria water hyacinth.

> **Status: early development.** The satellite-reading and first vegetation-mask steps work on a single scene. Hyacinth detection, the climate signal, the agent loop and the AWS deployment are not built yet. See [Status](#status).

---

## What it does (target design)

ZiwaClear already connects harvesters and buyers through SMS/USSD and M-Pesa. What it lacks is *where to send effort, and when*. ZiwaVision adds a perception and forecasting layer on top:

1. **Measure now:** use free Sentinel-2 imagery and OpenCV 5 to estimate hyacinth coverage per lake zone, and how fast it is changing.
2. **Anticipate:** use rainfall and temperature forecasts (via `acmadDL`) as a proxy for nutrient-runoff conditions that tend to precede faster growth. This is a stated, plausible assumption, not a validated causal finding.
3. **Decide and act:** an agent fuses both signals into a per-zone risk score. It checks its own confidence (retrying with another date or band when unsure), adjusts dispatch priority for moderate risk, and asks for human approval for high-stakes changes. Every step is logged.

ZiwaVision runs as a separate Python service. It writes results to a shared DynamoDB table, and ZiwaClear reads from it; the two systems never call each other directly.

Full design: see `ZiwaVision-Project-Brief.docx`.

---

## Status

| Area | State |
|---|---|
| Environment and project structure | Done |
| Search Sentinel-2 scenes (public AWS catalogue) | Done |
| Read bands for a small area; NDVI and vegetation mask | Done (single scene) |
| True-colour comparison image | Done |
| Read Scene Classification Layer (SCL) | In progress |
| Choose a scene that fully covers the test box | In progress |
| Cloud mask, lake detection, floating-vegetation mask | Not started |
| Coverage area per zone, trend over dates | Not started |
| Climate signal (`acmadDL`) and risk score | Not started |
| Agent loop with confidence check and approval gate | Not started |
| AWS: S3, Lambda/Fargate, DynamoDB, API Gateway | Not started |
| Graviton (COOL) vs x86 benchmark | Not started |
| Demo page, video, technical report | Not started |

Test site: **Dunga Beach, Winam Gulf** (lat -0.1667, lon 34.7833).

---

## Project structure

```
ZiwaVision/
├─ venv/                 # virtual environment (not committed)
├─ data/                 # downloaded files (not committed)
├─ outputs/              # generated images and results (not committed)
├─ src/
│  └─ explore_tile.py    # current script: find a scene, read bands, NDVI, comparison image
├─ requirements.txt
├─ README.md
├─ ZIWAVISION_GUIDE.md   # learning map: concepts used and what to study next
└─ PROGRESS.md           # personal log of what is understood and what to revisit
```

Planned modules as the code grows: `vision.py` (detection), `climate.py` (rainfall data), `risk.py` (risk score), `agent.py` (decision loop).

---

## Setup

Requires Python 3.12.

```bash
git clone <your-repo-url>
cd ZiwaVision
python -m venv venv
source venv/bin/activate          # Windows PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
mkdir -p outputs data
```

No API keys are needed for the current script: it reads open Sentinel-2 data from the public Earth Search catalogue. Later stages (AWS, Copernicus or climate APIs) will need credentials; keep those in environment variables or a `.env` file and never commit them.

### Minimal dependencies

The current script needs only:

```
numpy
opencv-python
rasterio
matplotlib
pystac-client
```

Planned: `acmadDL` (climate data) and `boto3` (AWS).

Your environment currently holds many other packages from a broader install. For a clean `requirements.txt`, create a fresh virtual environment, install only the packages above, then run `pip freeze > requirements.txt`.

---

## Run

```bash
python src/explore_tile.py
```

What it does:

1. Searches for Sentinel-2 L2A scenes over the bounding box (`BBOX`, ordered west, south, east, north) with under 20% cloud.
2. Prints each scene's date, cloud cover and ID, then picks one.
3. Reads the red, NIR, green and blue bands for just that box.
4. Computes NDVI and saves a vegetation mask to `outputs/ndvi_mask.png`.
5. Saves a side-by-side true-colour and mask image to `outputs/compare.png`.

### Known gotchas

- **Scene coverage:** Dunga sits near the edge between Sentinel-2 tiles. Some scenes (e.g. `36MYE`) cover only a strip of the box. Check that `red.shape` is close to `(1100, 1100)`; the `36MXE` scenes cover the full box.
- **Cloud cover is per tile**, not per box. Always check the true-colour image.
- **Working directory:** run from the project root so `outputs/` resolves correctly.
- **`cv2.imwrite` fails silently** if the folder doesn't exist.

---

## Limitations and assumptions

- Sentinel-2 pixels are 10 m. Whether that is fine enough to see hyacinth mats at a useful size is still an open check.
- NDVI alone cannot separate hyacinth from land vegetation or algae; the lake area has to be identified first.
- The Scene Classification Layer may label a floating mat as "vegetation" rather than "water".
- The rainfall-to-bloom link is an assumption, and thresholds are not yet validated.

---

## Roadmap

1. Pick a fully covering, clear scene; add a cloud and lake mask (SCL plus OpenCV morphology).
2. Isolate floating vegetation; measure area per zone; compare across dates.
3. Fetch rainfall data and compute a simple risk score.
4. Store results in S3/DynamoDB; run the vision workload on Graviton and x86 and record latency, throughput and cost.
5. Add the retry-on-low-confidence loop and the human-approval flag.
6. Demo page and endpoint, technical report, video.

---

## Credits and data

- Imagery: Copernicus Sentinel-2, served through Element84's Earth Search on AWS.
- Climate data (planned): `acmadDL`.
- Part of the ZiwaClear initiative.