"""
Intelligence Service — Phase 4 wrapper for the API layer.

Orchestrates the intelligence/ modules:
  - AnomalyDetector (surge / accident / road closure / sensor failure)
  - TrafficForecaster (Holt trend + congestion horizons)
  - IntersectionCoordinator (global PSO + green wave + emergency)
  - SignalControllerClient (controller push w/ fixed fallback)
  - TrafficManagementCenterClient (TMC data exchange + webhooks)

Keeps live observation history fed by the camera pipeline (or manual
counts posted via the API).
"""

from typing import Dict, Any, Optional

from utils.logger import LoggerManager
from utils.errors import TrafficAPIError

logger = LoggerManager.get_logger(__name__)


class IntelligenceService:
    """
    Facade over the Phase 4 intelligence modules.

    Usage:
        service = IntelligenceService()
        alerts = service.observe_counts({"north": 12, "south": 8, ...})
        service.forecast(steps=5)
    """

    def __init__(self):
        try:
            import os

            from intelligence.anomaly import AnomalyDetector
            from intelligence.forecaster import TrafficForecaster
            from intelligence.coordinator import IntersectionCoordinator
            from intelligence.controller import SignalControllerClient
            from intelligence.tmc import TrafficManagementCenterClient

            self.detector = AnomalyDetector()
            self.forecaster = TrafficForecaster()
            self.coordinator = IntersectionCoordinator()
            self.controller = SignalControllerClient()

            # Phase 5 Step 5.3: NTCIP-style adapter selected via
            # CONTROLLER_PROTOCOL=ntcip (default stays plain REST).
            self.protocol = (
                os.getenv("CONTROLLER_PROTOCOL", "rest").strip().lower()
            )
            if self.protocol == "ntcip":
                from intelligence.ntcip_adapter import NTCIPAdapter
                self.ntcip = NTCIPAdapter(
                    fallback_client=self.controller,
                )
                logger.info("Controller protocol: NTCIP-1202 adapter active")
            else:
                self.ntcip = None

            self.tmc = TrafficManagementCenterClient()
            self.available = True
            logger.info("IntelligenceService initialized (Phase 4 modules)")
        except Exception as e:
            logger.error(f"Failed to initialize IntelligenceService: {str(e)}")
            self.available = False

    # ── LIVE OBSERVATION ──────────────────────────────────────

    def observe_counts(self, counts: Dict[str, Any]) -> list:
        """
        Feed live per-direction counts to the detector + forecaster.

        Parameters
        ----------
        counts : dict
            {"north": n, "south": n, "east": n, "west": n, ...}

        Returns
        -------
        list
            Newly detected alerts.
        """
        if not self.available:
            return []
        if not counts:
            return []
        try:
            alerts = self.detector.update(counts)
            self.forecaster.observe(counts)
            return alerts
        except Exception as e:
            logger.error(f"observe_counts failed: {str(e)}")
            return []

    # ── ANOMALIES ─────────────────────────────────────────────

    def check_anomalies(self, counts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check anomalies for the given counts (and feed history)."""
        alerts = self.observe_counts(counts) if counts else []
        return {
            "alerts": alerts,
            "count": len(alerts),
            "detector": self.detector.get_status(),
            "pattern_check": self.detector.isolation_forest_anomaly(),
        }

    def anomaly_status(self) -> Dict[str, Any]:
        return {
            "detector": self.detector.get_status(),
            "pattern_check": self.detector.isolation_forest_anomaly(),
        }

    # ── FORECASTING ───────────────────────────────────────────

    def forecast(self, steps: int = 1,
                 counts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Forecast next N steps (optionally feeding new counts first)."""
        if counts:
            self.observe_counts(counts)
        return self.forecaster.forecast_next(steps)

    def congestion_forecast(self, minutes: Optional[int] = None) -> Dict[str, Any]:
        """Congestion levels at 5/10/15 minute horizons."""
        return self.forecaster.predict_congestion(minutes)

    # ── COORDINATION ──────────────────────────────────────────

    def optimize_intersections(self, demands: Dict[str, Any],
                               arterial: Optional[list] = None,
                               emergency: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Global PSO across multiple intersections."""
        if not demands:
            raise TrafficAPIError(
                message="demands must define at least one intersection",
                status_code=422,
                error_code="MISSING_FIELD",
                details={"missing_fields": ["demands"]},
            )
        return self.coordinator.optimize(demands, arterial=arterial, emergency=emergency)

    # ── CONTROLLER ────────────────────────────────────────────

    def apply_controller_timings(self, intersection_id: str,
                                 timings: Dict[str, Any],
                                 override: bool = False) -> Dict[str, Any]:
        """Push timings to the physical controller (fixed fallback on loss).

        Uses the NTCIP adapter when CONTROLLER_PROTOCOL=ntcip,
        otherwise the plain REST controller client.
        """
        if not intersection_id:
            raise TrafficAPIError(
                message="intersection_id is required",
                status_code=422,
                error_code="MISSING_FIELD",
                details={"missing_fields": ["intersection_id"]},
            )
        if not timings:
            raise TrafficAPIError(
                message="timings are required",
                status_code=422,
                error_code="MISSING_FIELD",
                details={"missing_fields": ["timings"]},
            )
        if getattr(self, "ntcip", None) is not None:
            return self.ntcip.apply_phase_timings(
                intersection_id, timings, override=override
            )
        return self.controller.apply_timings(intersection_id, timings, override=override)

    def controller_status(self) -> Dict[str, Any]:
        status = self.controller.get_status()
        if getattr(self, "ntcip", None) is not None:
            status["ntcip"] = self.ntcip.get_status()
        status["protocol"] = getattr(self, "protocol", "rest")
        return status

    # ── TMC (CITY INTEGRATION) ────────────────────────────────

    def tmc_status(self) -> Dict[str, Any]:
        """TMC client configuration and recent activity."""
        return self.tmc.get_status()