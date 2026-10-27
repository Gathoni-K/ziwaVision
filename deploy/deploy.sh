#!/usr/bin/env bash
# deploy/deploy.sh — ZiwaVision AWS backend deployment script
#
# Prerequisites:
#   aws CLI configured   (aws configure or ~/.aws/credentials)
#   AWS SAM CLI >= 1.105 (pip install aws-sam-cli)
#   Docker running       (required to build the Lambda container image)
#
#   SSM SecureString parameter holding the API key must exist BEFORE deployment:
#     aws ssm put-parameter \
#       --name /ziwavision/prod/api-key \
#       --type SecureString \
#       --value "<your-secret-key-min-16-chars>" \
#       --region eu-west-1
#
# Required environment variables:
#   AWS_ACCOUNT_ID — your 12-digit AWS account ID
#
# Optional environment variables:
#   BUCKET              (default: ziwavision; results bucket will be ${BUCKET}-results)
#   AWS_DEFAULT_REGION  (default: eu-west-1)
#   ECR_REPO            (default: ziwavision)
#   IMAGE_TAG           (default: latest)
#   STACK_NAME          (default: ziwavision)
#   SSM_API_KEY_PARAM   (default: /ziwavision/prod/api-key)
#
# Usage:
#   export AWS_ACCOUNT_ID=891858636219
#   export AWS_DEFAULT_REGION=eu-west-1
#   export BUCKET=ziwavision-results-gathoni
#   bash deploy/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET="${BUCKET:-ziwavision}"
RESULTS_BUCKET="${RESULTS_BUCKET:-${BUCKET}-results}"
REGION="${AWS_DEFAULT_REGION:-eu-west-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:?ERROR: AWS_ACCOUNT_ID must be set}"
ECR_REPO="${ECR_REPO:-ziwavision}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
STACK_NAME="${STACK_NAME:-ziwavision}"
SSM_API_KEY_PARAM="${SSM_API_KEY_PARAM:-/ziwavision/prod/api-key}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPO}:${IMAGE_TAG}"

echo "=========================================="
echo "ZiwaVision AWS Backend Deployment"
echo "Results Bucket Base: $BUCKET"
echo "Region:              $REGION"
echo "Image URI:           $IMAGE_URI"
echo "Stack:               $STACK_NAME"
echo "=========================================="

# ── 0. Validate SSM parameter exists ────────────────────────────────────────
echo ""
echo "[0] Checking SSM parameter ${SSM_API_KEY_PARAM} in region ${REGION}..."
if ! aws ssm get-parameter --name "$SSM_API_KEY_PARAM" \
     --region "$REGION" --query "Parameter.Name" --output text > /dev/null 2>&1; then
  echo "ERROR: SSM parameter '${SSM_API_KEY_PARAM}' not found or not accessible in region '${REGION}'."
  echo "Create it securely with:"
  echo "  aws ssm put-parameter \\"
  echo "    --name '${SSM_API_KEY_PARAM}' \\"
  echo "    --type SecureString \\"
  echo "    --value '<your-secret-key-min-16-chars>' \\"
  echo "    --region '${REGION}'"
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

# ── 2. Ensure ECR repository exists ──────────────────────────────────────────
echo ""
echo "[2] Ensuring ECR repository '${ECR_REPO}' exists..."
if ! aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1; then
  echo "   Creating ECR repository '${ECR_REPO}' in ${REGION}..."
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 >/dev/null
  echo "   ✓ ECR repository created."
else
  echo "   ✓ ECR repository '${ECR_REPO}' exists."
fi

# ── 3. Authenticate Docker with ECR ───────────────────────────────────────────
echo ""
echo "[3] Authenticating Docker with ECR..."
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# ── 4. Build the container image ─────────────────────────────────────────────
echo ""
echo "[4] Building Lambda container image (linux/amd64)..."
# Build context is the repository root so the Dockerfile can COPY src/ and
# deploy/lambda_requirements.txt from their correct relative paths.
docker build \
  --platform linux/amd64 \
  --provenance=false \
  --file "$ROOT/deploy/Dockerfile" \
  --tag "${ECR_REPO}:${IMAGE_TAG}" \
  "$ROOT"

# ── 5. Tag and push image to ECR ──────────────────────────────────────────────
echo ""
echo "[5] Tagging and pushing image to ECR..."
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"
echo "   ✓ Pushed: $IMAGE_URI"

# ── 6. SAM deploy (image-based; uses --resolve-s3 to manage packaging bucket) ─
echo ""
echo "[6] Deploying Lambda + API Gateway via SAM..."
sam deploy \
  --template-file "$ROOT/deploy/template.yaml" \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --resolve-s3 \
  --resolve-image-repos \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    BucketName="$BUCKET" \
    Environment=prod \
    ApiKeyParamName="$SSM_API_KEY_PARAM" \
    ImageUri="$IMAGE_URI" \
  --no-fail-on-empty-changeset

# ── 7. Retrieve stack outputs ─────────────────────────────────────────────────
echo ""
echo "[7] Retrieving stack outputs..."
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)

RESULTS_BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ResultsBucketName'].OutputValue" \
  --output text)

LAMBDA_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionName'].OutputValue" \
  --output text)

LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionArn'].OutputValue" \
  --output text)

# ── 8. Upload results + overlays to private results bucket ─────────────────────
RESULTS_BUCKET_TARGET="${RESULTS_BUCKET_NAME:-$RESULTS_BUCKET}"
echo ""
echo "[8] Uploading results.json to private results bucket (${RESULTS_BUCKET_TARGET})..."
aws s3 cp "$ROOT/outputs/results.json" "s3://$RESULTS_BUCKET_TARGET/data/results.json" \
  --region "$REGION" \
  --content-type "application/json"

if [ -d "$ROOT/outputs/overlays" ]; then
  echo "    Uploading overlay images to private results bucket..."
  aws s3 sync "$ROOT/outputs/overlays/" "s3://$RESULTS_BUCKET_TARGET/overlays/" \
    --region "$REGION"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "✓ Backend deployment complete!"
echo ""
echo "Deployed AWS Resources:"
echo "  API Gateway URL:        $API_URL"
echo "  Private Results Bucket: $RESULTS_BUCKET_NAME"
echo "  Lambda Function Name:   $LAMBDA_NAME"
echo "  Lambda Function ARN:    $LAMBDA_ARN"
echo "  Health Endpoint:        $API_URL/health"
echo ""
echo "Frontend Configuration (Vercel):"
echo "  Set the following environment variable in your Vercel project:"
echo "    VITE_API_BASE_URL=$API_URL"
echo "=========================================="
