FROM python:3.11-slim

# poppler: scanned-PDF rendering (pdf2image). libgl1/libglib2.0-0: needed by the OCR engine's OpenCV.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home app && mkdir -p /app/storage_data && chown -R app /app
USER app

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl -fs http://localhost:${PORT:-8001}/api/health || exit 1

# Apply database migrations, then start the API. Render sets $PORT.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --proxy-headers --forwarded-allow-ips='*'"]
