#!/usr/bin/env bash
# deploy/deploy.sh — ZiwaVision AWS deployment script
#
# Prerequisites:
#   aws CLI configured   (aws configure or ~/.aws/credentials)
#   AWS SAM CLI >= 1.105 (pip install aws-sam-cli)
#   Docker running       (required to build the Lambda container image)
#   AWS ECR repository   (create once: aws ecr create-repository --repository-name ziwavision)
#
#   SSM SecureString parameter holding the API key must exist BEFORE deployment:
#     aws ssm put-parameter \
#       --name /ziwavision/prod/api-key \
#       --type SecureString \
#       --value "<your-secret-key-min-16-chars>"
#
# Required environment variables:
#   BUCKET         — unique S3 bucket name (also used as the CloudFormation parameter)
#   AWS_ACCOUNT_ID — your 12-digit AWS account ID
#
# Optional environment variables:
#   AWS_DEFAULT_REGION  (default: us-east-1)
#   ECR_REPO            (default: ziwavision)
#   IMAGE_TAG           (default: latest)
#   STACK_NAME          (default: ziwavision)
#   SSM_API_KEY_PARAM   (default: /ziwavision/prod/api-key)
#
# Usage:
#   export BUCKET=ziwavision-yourname-2026
#   export AWS_ACCOUNT_ID=123456789012
#   bash deploy/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET="${BUCKET:-ziwavision-dashboard}"
RESULTS_BUCKET="${RESULTS_BUCKET:-${BUCKET}-results}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:?ERROR: AWS_ACCOUNT_ID must be set}"
ECR_REPO="${ECR_REPO:-ziwavision}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STACK_NAME="${STACK_NAME:-ziwavision}"
SSM_API_KEY_PARAM="${SSM_API_KEY_PARAM:-/ziwavision/prod/api-key}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"
SAM_BUILD_DIR="$ROOT/.aws-sam"

echo "=========================================="
echo "ZiwaVision AWS Deployment"
echo "Bucket:    $BUCKET"
echo "Region:    $REGION"
echo "Image URI: $IMAGE_URI"
echo "Stack:     $STACK_NAME"
echo "=========================================="

# ── 0. Validate SSM parameter exists ────────────────────────────────────────
echo ""
echo "[0] Checking SSM parameter ${SSM_API_KEY_PARAM}..."
if ! aws ssm get-parameter --name "$SSM_API_KEY_PARAM" --with-decryption \
     --region "$REGION" --query "Parameter.Value" --output text > /dev/null 2>&1; then
  echo "ERROR: SSM parameter '${SSM_API_KEY_PARAM}' not found or not accessible."
  echo "Create it with:"
  echo "  aws ssm put-parameter --name '${SSM_API_KEY_PARAM}' --type SecureString --value '<your-key>'"
  exit 1
fi
echo "   ✓ SSM parameter found."

# ── 1. Run pipeline if results.json is missing ────────────────────────────────
if [ ! -f "$ROOT/outputs/results.json" ]; then
  echo ""
  echo "[1] Running pipeline to generate results.json..."
  cd "$ROOT"
  source venv/bin/activate 2>/dev/null || true
  python src/run_pipeline.py
else
  echo "[1] results.json exists — skipping pipeline run."
fi

# ── 2. Build and push the container image ─────────────────────────────────────
echo ""
echo "[2] Authenticating Docker with ECR..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo ""
echo "[3] Building Lambda container image..."
# Build context is the repository root so the Dockerfile can COPY src/ and
# deploy/lambda_requirements.txt from their correct relative paths.
docker build \
  --platform linux/amd64 \
  --provenance=false \
  --file "$ROOT/deploy/Dockerfile" \
  --tag "${ECR_REPO}:${IMAGE_TAG}" \
  "$ROOT"

echo ""
echo "[4] Tagging and pushing image to ECR..."
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"
echo "   ✓ Pushed: $IMAGE_URI"

# ── 3. SAM deploy (image-based; no sam build step needed for pre-built image) ─
echo ""
echo "[5] Deploying Lambda + API Gateway via SAM..."
sam deploy \
  --template-file "$ROOT/deploy/template.yaml" \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --s3-bucket "$BUCKET" \
  --s3-prefix sam-packages \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    BucketName="$BUCKET" \
    Environment=prod \
    ApiKeyParamName="$SSM_API_KEY_PARAM" \
    ImageUri="$IMAGE_URI" \
  --no-fail-on-empty-changeset

# ── 4. Retrieve stack outputs ─────────────────────────────────────────────────
echo ""
echo "[6] Retrieving stack outputs..."
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

# ── 5. Build the Vite dashboard ───────────────────────────────────────────────
echo ""
echo "[7] Building Vite dashboard..."
# Inject the live API Gateway URL so the compiled JS bundle talks to prod,
# not localhost. This file is gitignored and generated fresh each deploy.
ENV_PROD="$ROOT/dashboard/.env.production"
if [ -n "$API_URL" ]; then
  echo "VITE_API_BASE_URL=$API_URL" > "$ENV_PROD"
  echo "   Wrote $ENV_PROD → VITE_API_BASE_URL=$API_URL"
fi
cd "$ROOT/dashboard"
npm install --silent
npm run build --silent
cd "$ROOT"

# ── 6. Sync dashboard/dist to S3 ─────────────────────────────────────────────
echo ""
echo "[8] Syncing dashboard/dist to S3..."
aws s3 sync "$ROOT/dashboard/dist/" "s3://$BUCKET/" \
  --acl public-read \
  --cache-control "max-age=300"

# ── 7. Upload results + overlays to private results bucket ─────────────────────
echo ""
echo "[9] Uploading results.json to private results bucket..."
aws s3 cp "$ROOT/outputs/results.json" "s3://$RESULTS_BUCKET/data/results.json" \
  --content-type "application/json"

if [ -d "$ROOT/outputs/overlays" ]; then
  echo "[10] Uploading overlay images to private results bucket..."
  aws s3 sync "$ROOT/outputs/overlays/" "s3://$RESULTS_BUCKET/overlays/"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "✓ Deployment complete!"
echo ""
echo "  Dashboard:  $DASHBOARD_URL"
echo "  API:        $API_URL"
echo "  Health:     $API_URL/health"
echo "=========================================="
