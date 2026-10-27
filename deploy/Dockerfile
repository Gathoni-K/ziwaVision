FROM public.ecr.aws/lambda/python:3.12

# Install native system libraries required by rasterio (GDAL) and OpenCV.
# libGL is not needed because we install opencv-python-headless below.
# libgomp is required by OpenCV parallel operations (GrabCut, morphology).
RUN dnf install -y \
      expat \
      glib2 \
      libgomp \
      libstdc++ \
    && dnf clean all

# Install lean Lambda runtime dependencies (see lambda_requirements.txt).
# The full requirements.txt is the local development venv dump and must NOT
# be used here — it is ~271 packages and would breach Lambda size limits.
COPY deploy/lambda_requirements.txt /tmp/lambda_requirements.txt
RUN pip install --no-cache-dir -r /tmp/lambda_requirements.txt

# Copy application source into the Lambda task root.
COPY src/ ${LAMBDA_TASK_ROOT}/

# Entry point: api.handler — Mangum wraps the Flask app for Lambda.
CMD ["api.handler"]
