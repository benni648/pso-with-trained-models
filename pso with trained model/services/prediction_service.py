"""
Prediction Service — wraps TrafficPredictor for API use.

Handles input validation, feature encoding, prediction execution,
and result logging.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any

from utils.logger import LoggerManager
from utils.errors import PredictionError, MissingFieldError, InvalidCongestionLevelError

logger = LoggerManager.get_logger(__name__)

# Valid congestion levels
VALID_CONGESTION_LEVELS = {"LOW", "MEDIUM", "HIGH"}

# Required input fields
REQUIRED_FIELDS = {"time_step", "hour", "density", "avg_wait_time", "congestion_level"}


class PredictionService:
    """
    Wraps the TrafficPredictor for use in the API layer.

    Usage:
        service = PredictionService()
        result = service.predict(input_data)
    """

    def __init__(self):
        """Initialize by loading the ML model."""
        self._camera_step_counter = 0
        try:
            from predict_traffic import TrafficPredictor
            self.predictor = TrafficPredictor()
            logger.info("PredictionService initialized successfully")
        except FileNotFoundError as e:
            logger.error(f"Model not found: {str(e)}")
            self.predictor = None
        except Exception as e:
            logger.error(f"Failed to initialize PredictionService: {str(e)}")
            self.predictor = None

    def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run ML prediction on input traffic data.

        Parameters
        ----------
        data : dict
            Input data with keys: time_step, hour, density, avg_wait_time, congestion_level.

        Returns
        -------
        dict
            Prediction results with vehicle counts per direction.

        Raises
        ------
        PredictionError
            If prediction fails.
        MissingFieldError
            If required fields are missing.
        InvalidCongestionLevelError
            If congestion_level is invalid.
        """
        if not self.predictor:
            raise PredictionError("Prediction service not available — model not loaded")

        # Validate input
        self._validate_input(data)

        # Run prediction
        start_time = time.time()
        try:
            result = self.predictor.predict(data)
            latency_ms = (time.time() - start_time) * 1000

            result["latency_ms"] = round(latency_ms, 2)

            # Phase 3: record latency metric (no-op without prometheus-client)
            try:
                from monitoring.metrics import Metrics
                Metrics.record_prediction(latency_ms / 1000.0)
            except ImportError:
                pass

            logger.info(
                f"Prediction successful — "
                f"N={result.get('north_vehicles', 0):.2f} "
                f"S={result.get('south_vehicles', 0):.2f} "
                f"E={result.get('east_vehicles', 0):.2f} "
                f"W={result.get('west_vehicles', 0):.2f} "
                f"({latency_ms:.1f}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            raise PredictionError(f"Prediction failed: {str(e)}")

    def predict_from_camera_counts(self, counts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict next-step traffic from vision pipeline zone counts.

        Builds a prediction request from the raw camera counts
        (north/south/east/west) by deriving the missing model inputs
        (hour, density, congestion level) from the current time and
        the observed volume.

        Parameters
        ----------
        counts : dict
            Zone counts from the vision pipeline, e.g.
            {"north": 12, "south": 8, "east": 15, "west": 6}.

        Returns
        -------
        dict
            Prediction results with vehicle counts per direction.
        """
        if not counts:
            raise PredictionError("Camera counts are empty")

        total = sum(
            v for k, v in counts.items()
            if k != "total" and isinstance(v, (int, float))
        )

        now = datetime.now()
        self._camera_step_counter += 1

        # Derive model inputs from observed volume
        density = round(min(1.0, total / 40.0), 4)
        if total >= 30:
            congestion = "HIGH"
        elif total >= 15:
            congestion = "MEDIUM"
        else:
            congestion = "LOW"

        data = {
            "time_step": self._camera_step_counter,
            "hour": now.hour,
            "density": density,
            "avg_wait_time": round(20.0 + density * 40.0, 2),
            "congestion_level": congestion,
        }

        logger.info(
            f"Camera prediction request derived from counts "
            f"{ {k: v for k, v in counts.items() if k != 'total'} }: {data}"
        )

        result = self.predict(data)
        # Expose the derived input for transparency / debugging
        result["input_data"] = data
        return result

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.

        Returns
        -------
        dict
            Model metadata: name, version, metrics.
        """
        info = {
            "name": "unknown",
            "version": "1.0",
            "loaded": self.predictor is not None,
        }

        if self.predictor and hasattr(self.predictor, "meta"):
            info.update({
                "metrics": self.predictor.meta.get("random_forest_metrics", {}),
                "recommended_model": self.predictor.meta.get("recommended_model", "rf_model.pkl"),
            })

        return info

    def _validate_input(self, data: Dict[str, Any]):
        """Validate input data fields."""
        if not data:
            raise MissingFieldError(list(REQUIRED_FIELDS))

        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            raise MissingFieldError(list(missing))

        congestion = str(data.get("congestion_level", "")).upper()
        if congestion not in VALID_CONGESTION_LEVELS:
            raise InvalidCongestionLevelError(congestion)
