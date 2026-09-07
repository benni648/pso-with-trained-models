"""
=====================================================================
 Traffic Forecasting — Phase 4 (Steps 4.1 + 4.4)
=====================================================================
 Short-horizon forecasting of per-direction vehicle counts using
 Holt's double exponential smoothing (level + trend). Provides:

   - forecast_next(steps)  → next-N-step per-direction counts
   - predict_congestion(minutes) → LOW / MEDIUM / HIGH at 5/10/15 min

 The engine interface keeps the door open for richer models (LSTM /
 Transformer / AutoML — see intelligence/deep_model.py for a
 torch-based LSTM companion). Congestion thresholds mirror the rest
 of the system: <15 vehicles LOW, 15-29 MEDIUM, >= 30 HIGH.
=====================================================================
"""

import threading
from collections import deque
from typing import Dict, Any, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

DIRECTIONS = ["north", "south", "east", "west"]

# Congestion thresholds based on current zone totals
LOW_MEDIUM_THRESHOLD = 15
MEDIUM_HIGH_THRESHOLD = 30

# Supported look-ahead horizons (minutes)
HORIZONS_MIN = [5, 10, 15]


class TrafficForecaster:
    """
    Incremental per-direction traffic forecaster.

    Usage:
        forecaster = TrafficForecaster()
        forecaster.observe({"north": 12, "south": 8, ...})
        forecast = forecaster.forecast_next(steps=5)
        congestion = forecaster.predict_congestion(minutes=15)
    """

    def __init__(self, history_size: int = 60,
                 alpha: float = 0.4, beta: float = 0.3):
        """
        Parameters
        ----------
        history_size : int
            Max readings kept per direction.
        alpha : float
            Level smoothing factor (0-1).
        beta : float
            Trend smoothing factor (0-1).
        """
        self.history_size = history_size
        self.alpha = alpha
        self.beta = beta
        self.history: Dict[str, deque] = {
            d: deque(maxlen=history_size) for d in DIRECTIONS
        }
        self._lock = threading.Lock()

    # ── FEEDING ───────────────────────────────────────────────

    def observe(self, counts: Dict[str, Any]) -> None:
        """
        Record the latest per-direction counts.

        Parameters
        ----------
        counts : dict
            {"north": n, "south": n, "east": n, "west": n}
        """
        with self._lock:
            for direction in DIRECTIONS:
                raw = counts.get(direction)
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if value >= 0:
                    self.history[direction].append(value)

    # ── FORECASTING ───────────────────────────────────────────

    def forecast_next(self, steps: int = 1) -> Dict[str, Any]:
        """
        Forecast vehicle counts for the next N steps (Holt smoothing).

        Parameters
        ----------
        steps : int
            Number of future steps to forecast (default 1).

        Returns
        -------
        dict
            {"steps": [...], "per_direction": {...}, "method": "holt"}
            Each step entry: {"step": n, "north_vehicles": ..., "total": ...}
        """
        steps = max(1, int(steps))
        per_direction: Dict[str, List[float]] = {}

        with self._lock:
            for direction in DIRECTIONS:
                values = list(self.history[direction])
                if len(values) < 3:
                    per_direction[direction] = [0.0] * steps
                    continue

                level, trend = self._holt_fit(values)
                per_direction[direction] = [
                    max(0.0, round(level + trend * (s + 1), 2))
                    for s in range(steps)
                ]

        series = []
        for s in range(steps):
            point = {"step": s + 1}
            total = 0.0
            for direction in DIRECTIONS:
                point[f"{direction}_vehicles"] = per_direction[direction][s]
                total += per_direction[direction][s]
            point["total"] = round(total, 2)
            series.append(point)

        return {"steps": series, "per_direction": per_direction, "method": "holt"}

    def predict_congestion(self, minutes: Optional[int] = None) -> Dict[str, Any]:
        """
        Predict congestion levels at 5 / 10 / 15 minute horizons.

        Uses the Holt forecast extrapolated to the requested horizon,
        where each step represents one observation interval.

        Parameters
        ----------
        minutes : int, optional
            Single horizon; if None, all 5/10/15 horizons are returned.

        Returns
        -------
        dict
            {"horizons": {"5": {...}, "10": {...}, "15": {...}}}
            Each horizon: {"minutes", "predicted_total", "level",
                            "per_direction"}
        """
        horizons = [minutes] if minutes else HORIZONS_MIN
        result = {}

        for horizon in horizons:
            if not horizon or horizon <= 0:
                continue
            # ~1 observation per minute for the camera cadence
            steps = max(1, int(round(horizon / 1.0)))
            forecast = self.forecast_next(steps)
            predicted_total = forecast["steps"][-1]["total"]
            level = self._level_for_total(predicted_total)
            result[str(horizon)] = {
                "minutes": horizon,
                "predicted_total": predicted_total,
                "level": level,
                "per_direction": {
                    d: forecast["per_direction"][d][-1]
                    for d in DIRECTIONS
                },
            }

        return {"horizons": result}

    # ── HELPERS ───────────────────────────────────────────────

    def _holt_fit(self, values: List[float]):
        """
        Fit Holt (double exponential smoothing) level & trend.

        Returns
        -------
        tuple
            (level, trend) at the last observation.
        """
        level = values[0]
        trend = values[1] - values[0] if len(values) > 1 else 0.0

        for i in range(1, len(values)):
            prev_level = level
            level = self.alpha * values[i] + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * trend

        return level, trend

    @staticmethod
    def _level_for_total(total: float) -> str:
        """Map a predicted vehicle total to a congestion level."""
        if total >= MEDIUM_HIGH_THRESHOLD:
            return "HIGH"
        if total >= LOW_MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    def get_status(self) -> Dict[str, Any]:
        """History lengths and method metadata."""
        return {
            "method": "holt",
            "history_lengths": {d: len(v) for d, v in self.history.items()},
            "history_size": self.history_size,
        }