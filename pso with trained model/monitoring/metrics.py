"""
=====================================================================
 Metrics — Prometheus Monitoring
=====================================================================
 Exposes production metrics for Prometheus scraping:

   - HTTP request count (by method / endpoint / status)
   - Prediction & optimization latency histograms
   - Active WebSocket connections gauge
   - Model accuracy gauge

 All imports of prometheus-client are lazy, so the application runs
 fine without it (metrics export is simply disabled).
=====================================================================
"""

import threading

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class Metrics:
    """Registry of Prometheus metric objects (created lazily)."""

    _lock = threading.Lock()
    _initialized = False

    requests_total = None
    prediction_latency = None
    optimization_latency = None
    active_connections = None
    model_accuracy = None

    @classmethod
    def initialize(cls):
        """Create metric objects if prometheus-client is available."""
        if cls._initialized:
            return True

        with cls._lock:
            if cls._initialized:
                return True
            try:
                from prometheus_client import Counter, Histogram, Gauge

                cls.requests_total = Counter(
                    "pso_http_requests_total",
                    "Total HTTP requests",
                    ["method", "endpoint", "status"],
                )
                cls.prediction_latency = Histogram(
                    "pso_prediction_latency_seconds",
                    "Traffic prediction latency in seconds",
                    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
                )
                cls.optimization_latency = Histogram(
                    "pso_optimization_latency_seconds",
                    "PSO optimization latency in seconds",
                    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
                )
                cls.active_connections = Gauge(
                    "pso_active_connections",
                    "Active WebSocket connections",
                )
                cls.model_accuracy = Gauge(
                    "pso_model_accuracy",
                    "Loaded model R² accuracy",
                )
                cls._initialized = True
                logger.info("Prometheus metrics initialized")
                return True
            except ImportError:
                logger.warning(
                    "prometheus-client not installed — metrics export disabled. "
                    "Install with: pip install prometheus-client"
                )
                return False
            except Exception as e:
                logger.warning(f"Metrics initialization failed: {str(e)}")
                return False

    @classmethod
    def record_prediction(cls, latency_seconds: float):
        """Record a prediction latency observation."""
        if cls._initialized and cls.prediction_latency is not None:
            cls.prediction_latency.observe(latency_seconds)

    @classmethod
    def record_optimization(cls, latency_seconds: float):
        """Record an optimization latency observation."""
        if cls._initialized and cls.optimization_latency is not None:
            cls.optimization_latency.observe(latency_seconds)

    @classmethod
    def set_model_accuracy(cls, accuracy: float):
        """Set the loaded model's accuracy gauge."""
        if cls._initialized and cls.model_accuracy is not None:
            cls.model_accuracy.set(accuracy)

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._initialized


def register_metrics(app):
    """
    Register the /metrics endpoint and request middleware.

    Parameters
    ----------
    app : Flask
        The Flask application instance.

    Returns
    -------
    bool
        True if Prometheus metrics were enabled.
    """
    if not Metrics.initialize():
        return False

    from flask import request

    @app.route("/metrics")
    def metrics_endpoint():
        """Expose metrics in Prometheus text format."""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.after_request
    def record_request(response):
        """Count every HTTP request by method / endpoint / status."""
        try:
            if Metrics.requests_total is not None:
                endpoint = request.endpoint or request.path
                Metrics.requests_total.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=str(response.status_code),
                ).inc()
        except Exception:
            pass
        return response

    logger.info("Metrics endpoint registered at /metrics")
    return True