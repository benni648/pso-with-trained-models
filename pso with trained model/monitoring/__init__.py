"""
Monitoring Package — Prometheus metrics export.

Provides production metrics (request counts, prediction/optimization
latency, active connections, model accuracy) and a /metrics endpoint
for Prometheus scraping. Degrades gracefully when the
prometheus-client library is not installed.
"""

from monitoring.metrics import register_metrics, Metrics

__all__ = ["register_metrics", "Metrics"]