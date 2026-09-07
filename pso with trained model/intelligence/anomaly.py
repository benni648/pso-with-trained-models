"""
=====================================================================
 Anomaly Detection — Phase 4 (Step 4.2)
=====================================================================
 Detects unusual traffic patterns per direction:

   - SURGE         → unusually high volume (special events)
   - ACCIDENT      → sudden drop in flow
   - ROAD_CLOSURE  → sustained zero vehicles in a direction
   - SENSOR_FAILURE→ impossible readings (negative / NaN / absurd)

 Detection methods:
   - Statistical: rolling mean / std + z-score per direction
   - Isolation Forest: pattern-level outliers over recent windows
     (used when enough history exists; sklearn loaded lazily)

 Alerts are raised once per episode (duplicate suppression) and carry
 a dashboard-friendly payload for the existing Socket.IO 'alert'
 events and the event bus.
=====================================================================
"""

import math
import threading
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

DIRECTIONS = ["north", "south", "east", "west"]

# Z-score above which a single value is considered an outlier
SURGE_Z_THRESHOLD = 2.5
DROP_Z_THRESHOLD = -2.5
# Consecutive zero readings before flagging a road closure
CLOSURE_MIN_ZEROS = 3
# Minimum samples before statistical detection activates
MIN_WINDOW = 6
# Values above this are treated as sensor faults
MAX_PLAUSIBLE_VEHICLES = 200


class AnomalyDetector:
    """
    Incremental per-direction anomaly detection.

    Usage:
        detector = AnomalyDetector()
        alerts = detector.update({"north": 12, "south": 8, ...})
        # list of alert dicts (empty when nothing unusual)
    """

    def __init__(self, window: int = 20, closure_min_zeros: int = CLOSURE_MIN_ZEROS):
        self.window = window
        self.closure_min_zeros = closure_min_zeros
        self.history: Dict[str, deque] = {
            d: deque(maxlen=window) for d in DIRECTIONS
        }
        self._zero_streaks: Dict[str, int] = {d: 0 for d in DIRECTIONS}
        self._closure_alerted: Dict[str, bool] = {d: False for d in DIRECTIONS}
        self._recent_alerts: deque = deque(maxlen=200)
        self._lock = threading.Lock()

    # ── PUBLIC API ─────────────────────────────────────────────

    def update(self, counts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Feed the latest per-direction counts and return new alerts.

        Parameters
        ----------
        counts : dict
            {"north": n, "south": n, "east": n, "west": n, ...}
            (a "total" key, if present, is ignored).

        Returns
        -------
        list[dict]
            Newly raised alerts since the last call.
        """
        alerts: List[Dict[str, Any]] = []

        with self._lock:
            for direction in DIRECTIONS:
                raw = counts.get(direction)
                if raw is None:
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = float("nan")

                # 1. Sensor failure: impossible readings
                if not math.isfinite(value) or value < 0 or value > MAX_PLAUSIBLE_VEHICLES:
                    alert = self._make_alert(
                        "SENSOR_FAILURE",
                        f"Sensor failure on {direction.upper()}: "
                        f"impossible reading {raw!r}",
                        severity="CRITICAL",
                        direction=direction,
                        value=raw,
                    )
                    if self._is_new(alert):
                        alerts.append(alert)
                    continue

                # 2. Road closure: sustained zeros after activity
                if value == 0:
                    self._zero_streaks[direction] += 1
                    if (self._zero_streaks[direction] >= self.closure_min_zeros
                            and self._was_active(direction)
                            and not self._closure_alerted[direction]):
                        alert = self._make_alert(
                            "ROAD_CLOSURE",
                            f"Possible road closure on {direction.upper()} — "
                            f"no vehicles for {self._zero_streaks[direction]} "
                            f"consecutive readings",
                            severity="HIGH",
                            direction=direction,
                            value=0,
                        )
                        alerts.append(alert)
                        self._closure_alerted[direction] = True
                    # Keep zeros out of the baseline window? They ARE real —
                    # store but avoid detecting drops off zero baselines.
                    self.history[direction].append(value)
                    continue

                self._zero_streaks[direction] = 0
                self._closure_alerted[direction] = False

                # 3. Statistical z-score: surge or sudden drop
                self.history[direction].append(value)
                z = self._zscore(direction, value)
                if z is None:
                    continue

                if z >= SURGE_Z_THRESHOLD and value >= 5:
                    alert = self._make_alert(
                        "SURGE",
                        f"Traffic surge on {direction.upper()} — "
                        f"{value:.0f} vehicles (z={z:.1f})",
                        severity="MEDIUM",
                        direction=direction,
                        value=value,
                        z_score=round(z, 2),
                    )
                    alerts.append(alert)
                elif z <= DROP_Z_THRESHOLD and self._recent_mean(direction, before_last=False) >= 3:
                    alert = self._make_alert(
                        "ACCIDENT",
                        f"Sudden flow drop on {direction.upper()} — "
                        f"{value:.0f} vehicles (z={z:.1f}). Possible accident.",
                        severity="HIGH",
                        direction=direction,
                        value=value,
                        z_score=round(z, 2),
                    )
                    alerts.append(alert)

        for alert in alerts:
            self._recent_alerts.append(alert)
            logger.warning(
                f"[{alert['severity']}] {alert['type']}: {alert['message']}"
            )

        return alerts

    def analyze_window(self, series: Dict[str, List[float]]) -> List[Dict[str, Any]]:
        """
        Stateless anomaly scan over a full window of historical counts.

        Useful for auditing / API inspection of a data window.

        Parameters
        ----------
        series : dict
            {direction: [values...]} — needs ≥ 5 points per direction.

        Returns
        -------
        list[dict]
            Anomaly markers with index, direction, value, z-score.
        """
        results: List[Dict[str, Any]] = []
        for direction, values in series.items():
            if len(values) < 5:
                continue
            clean = [float(v) for v in values if v is not None]
            if not clean:
                continue
            mean = sum(clean) / len(clean)
            std = (sum((v - mean) ** 2 for v in clean) / len(clean)) ** 0.5 or 1e-9
            for i, value in enumerate(values):
                if value is None:
                    continue
                z = (float(value) - mean) / std
                if abs(z) >= 2.5:
                    results.append({
                        "direction": direction,
                        "index": i,
                        "value": value,
                        "z_score": round(z, 2),
                        "type": "SURGE" if z > 0 else "ACCIDENT",
                    })
        return results

    def isolation_forest_anomaly(self, window: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Isolation-Forest based pattern check over recent history.

        Uses sklearn (lazy import). Returns
        {"score": float, "is_anomaly": bool, "used_isolation_forest": bool}
        or a graceful explanation when sklearn/history is unavailable.
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            return {"used_isolation_forest": False,
                    "reason": "sklearn not installed"}

        # Build a small feature matrix: for each history point, all directions
        hist = self._snapshot()
        if min(len(v) for v in hist.values()) < 10:
            return {"used_isolation_forest": False,
                    "reason": "insufficient history (need >= 10 per direction)"}

        rows = list(zip(*[list(hist[d]) for d in DIRECTIONS]))
        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(rows)
        # Score the latest point (lower = more anomalous)
        last = [hist[d][-1] for d in DIRECTIONS]
        score = float(model.score_samples([last])[0])
        return {
            "used_isolation_forest": True,
            "score": round(score, 4),
            "is_anomaly": bool(model.predict([last])[0] == -1),
            "latest": dict(zip(DIRECTIONS, last)),
        }

    def get_status(self) -> Dict[str, Any]:
        """History length per direction and recent alerts."""
        return {
            "window": self.window,
            "history_lengths": {d: len(v) for d, v in self.history.items()},
            "recent_alerts": list(self._recent_alerts)[-20:],
        }

    # ── INTERNALS ──────────────────────────────────────────────

    def _zscore(self, direction: str, value: float) -> Optional[float]:
        values = list(self.history[direction])
        if len(values) < MIN_WINDOW:
            return None
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        if std < 1e-6:
            return None
        return (value - mean) / std

    def _recent_mean(self, direction: str, before_last: bool = True) -> float:
        values = list(self.history[direction])
        if before_last:
            values = values[:-1]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _was_active(self, direction: str) -> bool:
        """True if the direction had meaningful traffic before going silent."""
        values = list(self.history[direction])
        # Look at the last non-zero stretch before the current zero streak
        return any(v >= 1 for v in values[-self.window:])

    def _is_new(self, alert: Dict[str, Any]) -> bool:
        """Deduplicate: skip an identical open alert for the same episode."""
        for existing in self._recent_alerts:
            if (existing["type"] == alert["type"]
                    and existing.get("direction") == alert.get("direction")):
                # Same episode → not new (road closure / sensor failure repeat)
                if alert["type"] in ("ROAD_CLOSURE", "SENSOR_FAILURE"):
                    return False
        return True

    def _snapshot(self) -> Dict[str, List[float]]:
        return {d: list(v) for d, v in self.history.items()}

    @staticmethod
    def _make_alert(alert_type: str, message: str, severity: str,
                    direction: str, value: Any, z_score: Optional[float] = None) -> Dict[str, Any]:
        return {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "direction": direction,
            "value": value,
            "z_score": z_score,
            "timestamp": datetime.utcnow().isoformat(),
        }