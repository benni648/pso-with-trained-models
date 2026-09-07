# =====================================================================
# Gunicorn — Production WSGI Configuration
# =====================================================================
# Used by the Docker image and bare-metal deployments:
#   gunicorn -c gunicorn.conf.py api.app:app
#
# When flask-socketio + eventlet are installed, use the eventlet
# worker for WebSocket support:
#   gunicorn -c gunicorn.conf.py -k eventlet api.app:app
# =====================================================================

import multiprocessing
import os

# ── Bind ───────────────────────────────────────────────────────
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '5000')}"

# ── Workers ────────────────────────────────────────────────────
# 2 × CPU cores + 1, capped at 8 for memory sanity
workers = min(int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1)), 8)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")  # "eventlet" for WebSockets
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = 120
graceful_timeout = 30

# ── Naming ─────────────────────────────────────────────────────
proc_name = "pso-traffic-api"

# ── Logging ────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# ── Reliability ────────────────────────────────────────────────
max_requests = 1000
max_requests_jitter = 100
preload_app = False
capture_output = True