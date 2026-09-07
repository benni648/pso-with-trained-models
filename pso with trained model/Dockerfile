# =====================================================================
# PSO Smart Traffic Signal Optimization — Production Image
# =====================================================================
FROM python:3.11-slim

# System dependencies (OpenCV runtime needs libgl, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for production
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV ENVIRONMENT=production \
    DEBUG=False \
    HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# gunicorn runs the Flask app (WebSocket support via eventlet worker
# when flask-socketio + eventlet are installed)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "api.app:app"]