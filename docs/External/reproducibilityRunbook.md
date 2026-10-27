# Reproducibility Runbook & Judge's Quick-Start
**OpenCV AI Competition 2026 Evaluation Guide**  
**Estimated Evaluation Time:** 5–10 minutes  

This step-by-step runbook enables technical competition judges to independently reproduce, verify, and interact with ZiwaVision from a fresh terminal.

---

## 1. System Requirements & Pinned Dependencies

- **Operating System:** Linux (Ubuntu 22.04+, Arch Linux, Debian 12+) or macOS (with Homebrew).
- **Python Version:** Python **3.12.7** (Python 3.12+ required for `acmadDL` and OpenCV 5 wheels).
- **Core Dependencies (Pinned in [`requirements.txt`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/requirements.txt)):**
  - `opencv-python==5.0.0.93` (OpenCV 5.0.0)
  - `rasterio==1.5.1`
  - `pystac-client==0.9.0`
  - `flask==3.1.3` & `flask-cors==6.0.5`
  - `boto3==1.43.75`
  - `mangum==0.19.0` (Lambda ASGI adapter — Lambda-only, optional locally)
  - `numpy==2.5.3` & `matplotlib==3.11.2`
- **Lambda Container (AWS only):** [`deploy/lambda_requirements.txt`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/deploy/lambda_requirements.txt) — lean 10-package subset used in the Docker image.
- **Node.js Environment (Dashboard):** Node.js 18+ and npm 9+.

---

## 2. Five-Minute Verification Walkthrough

### Step 1: Environment & Dependency Check
From the repository root:

```bash
# Activate virtual environment
source venv/bin/activate

# Verify Python version (must be >= 3.12)
python --version
# Expected: Python 3.12.x

# Verify OpenCV 5.0.0 is loaded
python -c "import cv2; print('OpenCV Version:', cv2.__version__)"
# Expected: OpenCV Version: 5.0.0
```

---

### Step 2: Run the Automated Test Suite (74 Tests)
Run pytest with a test API key configured:

```bash
ZIWAVISION_API_KEY=test-api-key-for-testing-only-12345 pytest tests/
```
**Expected Outcome:**
```
======================= 74 passed, 13 warnings in ~3.2s ========================
```
- Tests [`tests/test_detection.py`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/tests/test_detection.py): Confirms zero inland vegetation detections.
- Tests [`tests/test_inspector.py`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/tests/test_inspector.py): Confirms all agent tools, crop inspections, and routing gates.
- Tests [`tests/test_api.py`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/tests/test_api.py): Confirms API security, fail-closed auth, and review state machine.

---

### Step 3: Execute Live Satellite Data Demonstration
Run [`src/demonstrate_cases.py`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/src/demonstrate_cases.py) to connect live to Element84 Earth Search STAC, download real Sentinel-2 COG bands, and observe the Active Inspector in action:

```bash
python src/demonstrate_cases.py
```

**What to Observe:**
- **Case 1 (2026-08-23):** Downloads real bands, detects 1 candidate patch ($110.86\text{ ha}$), runs `alt_analysis`, detects visual disagreement ($\mathrm{IoU} = 0.141 < 0.70$), and escalates to `request_human_verification`.
- **Case 2 (2026-08-28):** Downloads real clear-lake baseline, detects large-area turbidity anomaly ($2,080.79\text{ ha} / 45.1\%$ of lake), invokes the area-anomaly guard, and terminates safely with `reject_mask_artifact`.
- **Case 3 (2026-08-29):** Queries STAC for an unobserved date, receives 0 items, and outputs an explicit structured failure trace (`access_failure`) without crashing.

---

### Step 4: Execute Controlled Fault-Injection Demonstration
Run [`src/run_fault_demo.py`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/src/run_fault_demo.py) to test system resilience against hostile operational faults:

```bash
python src/run_fault_demo.py
```

**Expected Outcome:**
Prints the real trace records and verification table for all 6 fault categories (Transient STAC failure, Retry exhaustion, Missing asset, Corrupted mask, Shape mismatch, and Step-limit termination).
```
====================================================================
  Trace confirmed: 6/6
  All six fault outcomes recorded safely. ✓
====================================================================
```

---

### Step 5: Start the API Backend Locally
To inspect the live REST API:

```bash
# Launch API on port 5050 with an explicit review API key
export ZIWAVISION_API_KEY="super-secret-judge-key-2026"
export PORT=5050
python src/api.py
```

In a second terminal, verify the live endpoints with `curl`:

```bash
# 1. Check health & auth status
curl -s http://127.0.0.1:5050/health
# Expected: {"auth_configured": true, "service": "ZiwaVision API", "status": "ok"}

# 2. Query hotspots list
curl -s http://127.0.0.1:5050/api/hotspots | jq '.[0]'

# 3. Retrieve audit trace for 2026-08-23
curl -s http://127.0.0.1:5050/api/traces/2026-08-23 | jq '.'

# 4. Attempt unauthenticated review (Must fail with 401)
curl -s -X POST http://127.0.0.1:5050/api/hotspots/s2c-36mxe-20260823-0-l2a/verify \
  -H "Content-Type: application/json" \
  -d '{"decision": "verified"}'
# Expected: {"error": "Missing or malformed Authorization header"} (HTTP 401)

# 5. Execute authorized review with bearer token (Must succeed with 200)
curl -s -X POST http://127.0.0.1:5050/api/hotspots/s2c-36mxe-20260823-0-l2a/verify \
  -H "Authorization: Bearer super-secret-judge-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"decision": "verified", "reviewer_id": "judge_1"}'
# Expected: {"status": "ok", "verification_status": "verified"} (HTTP 200)
```

---

### Step 6: Launch the Operator Web Dashboard
To view the interactive React interface:

```bash
cd dashboard

# Install dependencies (if not already installed)
npm install

# Start Vite dev server
npm run dev
```

Open your browser to `http://localhost:5173` (or the URL printed by Vite).

**Key Dashboard Features to Explore:**
1. **Interactive Hotspot Table:** Browse 12 multi-temporal acquisitions, sorted by observation date.
2. **Side-by-Side Satellite Overlays:** Inspect true-colour imagery aligned with OpenCV 5 candidate segmentation overlays.
3. **Audit Trail Inspector:** View the full step-by-step Active Inspector trace, showing exact OpenCV numerical measurements for every decision.
4. **Human Verification Controls:** Click "Verify Detection" or "Reject as Artefact" to test human-in-the-loop review.
5. **Offline Fallback:** If the API backend is stopped, the dashboard automatically detects connection loss and falls back gracefully to built-in static fixtures.

---

## 3. Common Troubleshooting Notes

| Symptom | Cause | Resolution |
|---|---|---|
| `pytest tests/test_api.py` returns 401 errors | `ZIWAVISION_API_KEY` is not set in the shell | Run with `ZIWAVISION_API_KEY=test-api-key-for-testing-only-12345 pytest tests/` |
| Port 5050 already in use | An instance of `src/api.py` is already running | Kill existing process with `pkill -f "python src/api.py"` or set `PORT=5051` |
| Rasterio COG download takes > 30s | Slower network connection to AWS Earth Search | Network latency is normal for multi-band downloads; bounded retries handle transient drops |
| `sam deploy` fails with `ImageUri is required` | SAM template uses image packaging; `ImageUri` must be supplied | Build and push the container first with Docker + ECR (automated by `bash deploy/deploy.sh`). See [`awsDeployment.md §3`](file:///home/grace/Projects/CODEINE/hackathonTingz/ZiwaVision/docs/External/awsDeployment.md) |
| Lambda returns 503 on `/verify` | `ZIWAVISION_API_KEY` SSM parameter not set or unreachable | Create the SSM SecureString: `aws ssm put-parameter --name /ziwavision/prod/api-key --type SecureString --value <key>` |
