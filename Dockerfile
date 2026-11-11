# Inquiry router image. Serving needs numpy and FastAPI only; torch stays in the training image.
FROM python:3.12-slim

RUN useradd --uid 10001 --create-home app
WORKDIR /app
COPY requirements-serve.txt ./
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY config ./config
COPY src ./src
# Air-gapped sites take the artifacts in the image; elsewhere the chart's init container pulls them by digest.
COPY artifacts /models

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SOV_REGISTRY=/models \
    PORT=8080
USER 10001
EXPOSE 8080
CMD ["python", "-m", "sov.serve.app"]
