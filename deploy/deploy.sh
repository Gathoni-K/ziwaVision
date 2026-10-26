#!/usr/bin/env bash
# deploy/deploy.sh — ZiwaVision AWS deployment script
#
# Prerequisites:
#   aws CLI configured (aws configure or ~/.aws/credentials)
#   AWS SAM CLI installed (pip install aws-sam-cli)
#   BUCKET env var set to a unique S3 bucket name
#
# Usage:
#   export BUCKET=ziwavision-yourname-2026
#   bash deploy/deploy.sh
#
# What it does:
#   1. Run the pipeline locally if results.json is missing.
#   2. Package and deploy the Lambda + API Gateway (SAM).
#   3. Patch the dashboard API_BASE to point at the API Gateway URL.
#   4. Sync the dashboard static files to S3.
#   5. Upload outputs/results.json and outputs/overlays/ to S3.
#   6. Print the public dashboard URL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUCKET="${BUCKET:-ziwavision-dashboard}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
STACK_NAME="ziwavision"
SAM_BUILD_DIR="$ROOT/.aws-sam"

echo "=========================================="
echo "ZiwaVision AWS Deployment"
echo "Bucket: $BUCKET"
echo "Region: $REGION"
echo "=========================================="

# ── 0. Install Mangum if not present ─────────────────────────────────────────
cd "$ROOT"
source venv/bin/activate 2>/dev/null || true
pip install mangum --quiet

# Patch api.py: uncomment the Mangum handler line
sed -i 's/^# from mangum/from mangum/' src/api.py
sed -i 's/^# handler = Mangum/handler = Mangum/' src/api.py

# ── 1. Run pipeline if results.json is missing ────────────────────────────────
if [ ! -f "$ROOT/outputs/results.json" ]; then
  echo ""
  echo "[1] Running pipeline to generate results.json…"
  cd "$ROOT/src"
  python run_pipeline.py
  cd "$ROOT"
else
  echo "[1] results.json already exists — skipping pipeline run."
fi

# ── 2. SAM build + deploy ─────────────────────────────────────────────────────
echo ""
echo "[2] Building SAM package…"
sam build \
  --template-file deploy/template.yaml \
  --build-dir "$SAM_BUILD_DIR" \
  --use-container

echo ""
echo "[3] Deploying Lambda + API Gateway…"
sam deploy \
  --template-file "$SAM_BUILD_DIR/template.yaml" \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --s3-bucket "$BUCKET" \
  --s3-prefix sam-packages \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    BucketName="$BUCKET" \
    Environment=prod \
  --no-fail-on-empty-changeset

# ── 3. Get API Gateway URL from stack outputs ─────────────────────────────────
echo ""
echo "[4] Retrieving API Gateway URL…"
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

DASHBOARD_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" \
  --output text)

echo "   API URL:       $API_URL"
echo "   Dashboard URL: $DASHBOARD_URL"

# ── 4. Build the Vite dashboard ──────────────────────────────────────────────────────
echo ""
echo "[5] Building Vite dashboard…"
# The API URL is injected into dashboard/.env.production before building
# so the compiled JS bundle talks to the real API Gateway, not localhost.
ENV_PROD="$ROOT/dashboard/.env.production"
if [ -n "$API_URL" ]; then
  echo "VITE_API_BASE_URL=$API_URL" > "$ENV_PROD"
  echo "   Wrote $ENV_PROD → VITE_API_BASE_URL=$API_URL"
fi
cd "$ROOT/dashboard"
npm install --silent
npm run build --silent
cd "$ROOT"

# ── 5. Sync dashboard/dist to S3 ───────────────────────────────────────────
echo ""
echo "[6] Syncing dashboard/dist to S3…"
# Sync the Vite build output (dashboard/dist/) — not the source tree.
aws s3 sync "$ROOT/dashboard/dist/" "s3://$BUCKET/" \
  --acl public-read \
  --cache-control "max-age=300"

# ── 6. Upload results + overlays ─────────────────────────────────────────────
echo ""
echo "[7] Uploading results.json to S3…"
aws s3 cp "$ROOT/outputs/results.json" "s3://$BUCKET/data/results.json" \
  --acl public-read \
  --content-type "application/json"

if [ -d "$ROOT/outputs/overlays" ]; then
  echo "[8] Uploading overlay images to S3…"
  aws s3 sync "$ROOT/outputs/overlays/" "s3://$BUCKET/overlays/" \
    --acl public-read
fi

# ── 7. Restore api.py (undo the Mangum uncomment for local dev) ───────────────
sed -i 's/^from mangum/# from mangum/' src/api.py
sed -i 's/^handler = Mangum/# handler = Mangum/' src/api.py

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "✓ Deployment complete!"
echo ""
echo "  Dashboard:  $DASHBOARD_URL"
echo "  API:        $API_URL"
echo "  Health:     $API_URL/health"
echo "=========================================="
