"""
Optimization Service — wraps PSOOptimizer for API use.

Handles input validation, PSO execution, and result logging.
"""

import time
from typing import Dict, Any

from utils.logger import LoggerManager
from utils.errors import OptimizationError, MissingFieldError

logger = LoggerManager.get_logger(__name__)

# Required vehicle count fields
REQUIRED_VEHICLE_FIELDS = {"north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"}


class OptimizationService:
    """
    Wraps the PSOOptimizer for use in the API layer.

    Usage:
        service = OptimizationService()
        result = service.optimize(vehicle_data)
    """

    def __init__(self):
        """Initialize by loading the PSO optimizer."""
        try:
            from pso_integration import PSOOptimizer
            self.optimizer = PSOOptimizer(n_particles=30, n_iterations=50)
            logger.info("OptimizationService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OptimizationService: {str(e)}")
            self.optimizer = None

    def optimize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run PSO optimization on vehicle count data.

        Parameters
        ----------
        data : dict
            Vehicle counts with keys: north_vehicles, south_vehicles,
            east_vehicles, west_vehicles.

        Returns
        -------
        dict
            Optimized signal timings with fitness score.

        Raises
        ------
        OptimizationError
            If optimization fails.
        MissingFieldError
            If required fields are missing.
        """
        if not self.optimizer:
            raise OptimizationError("Optimization service not available — PSO not loaded")

        # Validate input
        self._validate_input(data)

        # Ensure all values are numeric and non-negative
        clean_data = {}
        for key in REQUIRED_VEHICLE_FIELDS:
            value = float(data[key])
            clean_data[key] = max(0.0, value)

        # Run optimization
        start_time = time.time()
        try:
            result = self.optimizer.optimize(clean_data)
            duration_ms = (time.time() - start_time) * 1000

            result["duration_ms"] = round(duration_ms, 2)

            # Phase 3: record latency metric (no-op without prometheus-client)
            try:
                from monitoring.metrics import Metrics
                Metrics.record_optimization(duration_ms / 1000.0)
            except ImportError:
                pass

            logger.info(
                f"Optimization successful — "
                f"N={result.get('north_green', 0)}s "
                f"S={result.get('south_green', 0)}s "
                f"E={result.get('east_green', 0)}s "
                f"W={result.get('west_green', 0)}s "
                f"fitness={result.get('fitness', 0):.4f} "
                f"({duration_ms:.1f}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}")
            raise OptimizationError(f"Optimization failed: {str(e)}")

    def _validate_input(self, data: Dict[str, Any]):
        """Validate input data fields."""
        if not data:
            raise MissingFieldError(list(REQUIRED_VEHICLE_FIELDS))

        missing = REQUIRED_VEHICLE_FIELDS - set(data.keys())
        if missing:
            raise MissingFieldError(list(missing))
