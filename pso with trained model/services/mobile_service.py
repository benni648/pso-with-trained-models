"""
Mobile App Service — Phase 4 (Step 4.5)
========================================
Aggregated, read-only data feed designed for a commuter mobile app:

  - Real-time intersection status   (counts, congestion, timings)
  - Estimated travel times          (between registered points)
  - Incident reports                (anomaly alerts as incidents)

All endpoints behind this service are intentionally unauthenticated
(public/commuter data) and expose no operational controls.
"""

import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

MAX_INCIDENTS = 100


class MobileService:
    """
    Public commuter-facing data aggregation for the mobile app.

    Usage:
        service = MobileService()
        service.publish_snapshot({"north": 12, ...}, {"north_green": 30, ...})
        status = service.get_traffic_status()
    """

    def __init__(self, intelligence_service=None, health_monitor=None):
        self._intelligence = intelligence_service
        self._health = health_monitor
        self._lock = threading.Lock()
        self._latest: Dict[str, Any] = {}
        self._updated_at: Optional[float] = None
        self._incidents: deque = deque(maxlen=MAX_INCIDENTS)

    # ── INGESTION (called by the server internals) ────────────

    def publish_snapshot(self, counts: Optional[Dict[str, Any]] = None,
                         timings: Optional[Dict[str, Any]] = None,
                         intersection_id: str = "INT_001") -> None:
        """Record the latest counts/timings snapshot (from the camera
        pipeline callback or the simulation loop)."""
        with self._lock:
            self._latest = {
                "intersection_id": intersection_id,
                "counts": counts or {},
                "timings": timings or {},
            }
            self._updated_at = time.time()

    def publish_alert(self, alert: Dict[str, Any]) -> None:
        """Convert an anomaly/override alert into a public incident."""
        if not alert:
            return
        incident = {
            "id": f"INC_{int(time.time() * 1000)}",
            "type": str(alert.get("type", "UNKNOWN")),
            "severity": str(alert.get("severity", "LOW")),
            "message": str(alert.get("message", "")),
            "reported_at": datetime_utc_iso(),
        }
        with self._lock:
            self._incidents.appendleft(incident)

    # ── PUBLIC API ─────────────────────────────────────────────

    def get_traffic_status(self) -> Dict[str, Any]:
        """Current intersection status for the mobile dashboard."""
        status: Dict[str, Any] = {
            "intersection": {
                "id": "INT_001",
                "counts": {},
                "timings": {},
            },
            "updated_at": None,
            "live": False,
        }
        with self._lock:
            if self._latest:
                status["intersection"] = {
                    "id": self._latest.get("intersection_id", "INT_001"),
                    "counts": dict(self._latest.get("counts") or {}),
                    "timings": dict(self._latest.get("timings") or {}),
                }
                status["updated_at"] = self._updated_at
                # Fresh if updated within the last 30 seconds
                status["live"] = (time.time() - self._updated_at) < 30.0

        # Attach the forecaster's congestion view when available
        if self._intelligence is not None and getattr(self._intelligence, "available", False):
            try:
                congestion = self._intelligence.congestion_forecast()
                status["congestion_horizons"] = congestion.get("horizons", {})
            except Exception as e:
                logger.debug(f"Congestion attach failed: {str(e)}")
        return status

    def estimate_travel_time(self, distance_km: float,
                             congestion_level: str = "LOW") -> Dict[str, Any]:
        """
        Rough travel-time estimate for commuters.

        Parameters
        ----------
        distance_km : float
        congestion_level : str
            "LOW" | "MEDIUM" | "HIGH" (defaults to current forecast
            level when the caller omits it — see API layer).
        """
        try:
            distance_km = max(0.1, float(distance_km))
        except (TypeError, ValueError):
            distance_km = 1.0
        multipliers = {"LOW": 1.0, "MEDIUM": 1.5, "HIGH": 2.2}
        factor = multipliers.get(str(congestion_level).upper(), 1.0)
        # 40 km/h free-flow + signal delays (~0.5 min per km)
        base_minutes = distance_km / 40.0 * 60.0
        eta = base_minutes * factor + 0.5 * distance_km
        return {
            "distance_km": round(distance_km, 2),
            "congestion_level": str(congestion_level).upper(),
            "eta_minutes": round(eta, 1),
            "assumed_speed_kmh": round(distance_km / max(eta, 0.1) * 60.0, 1),
        }

    def get_incidents(self, limit: int = 20) -> Dict[str, Any]:
        """Recent public incidents (anomaly-derived)."""
        limit = max(1, min(int(limit), MAX_INCIDENTS))
        with self._lock:
            incidents = list(self._incidents)[:limit]
        return {"incidents": incidents, "count": len(incidents)}

    def get_app_summary(self) -> Dict[str, Any]:
        """Single-call summary payload for app home screens."""
        summary: Dict[str, Any] = {
            "traffic": self.get_traffic_status(),
            "incidents": self.get_incidents(limit=5),
        }
        if self._health is not None:
            try:
                health = self._health.get_system_health()
                summary["system"] = {
                    "server_status": health.get("server_status"),
                    "uptime": health.get("uptime"),
                }
            except Exception as e:
                logger.debug(f"Health summary skipped: {str(e)}")
        return summary


def datetime_utc_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()
