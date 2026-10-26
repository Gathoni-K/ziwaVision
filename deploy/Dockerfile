FROM public.ecr.aws/lambda/python:3.12

# Install native system libraries for OpenCV 5 and Rasterio
RUN dnf install -y mesa-libGL glib2 libgomp && dnf clean all

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt mangum

# Copy application source
COPY src/ ${LAMBDA_TASK_ROOT}/

CMD ["api.handler"]
