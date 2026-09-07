"""
System health monitoring for the PSO Traffic application.

Provides real-time system metrics:
  - Server uptime
  - Memory usage
  - CPU usage
  - Disk usage
  - Model loading status
  - Service availability
"""

import os
import time
from datetime import datetime
from typing import Dict, Any

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# Track server start time
_start_time = time.time()


class HealthMonitor:
    """
    Monitors system health and provides status information.

    Usage:
        monitor = HealthMonitor()
        health = monitor.get_system_health()
    """

    def __init__(self):
        self._start_time = _start_time

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health data.

        Returns
        -------
        dict
            Health data including uptime, memory, CPU, disk, model status.
        """
        health = {
            "server_status": "UP",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": self._get_uptime(),
            "api_version": self._get_api_version(),
            "model": self._get_model_status(),
            "resources": self._get_resource_usage(),
            "services": self._get_service_status(),
        }

        return health

    def _get_uptime(self) -> str:
        """Calculate formatted uptime string."""
        elapsed = time.time() - self._start_time
        days = int(elapsed // 86400)
        hours = int((elapsed % 86400) // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def _get_api_version(self) -> str:
        """Get API version from config."""
        try:
            from config.config import config
            return config.APP_VERSION
        except (ImportError, AttributeError):
            return "1.0.0"

    def _get_model_status(self) -> Dict[str, Any]:
        """Check if ML models are loaded."""
        try:
            from config.config import config
            model_dir = config.MODEL_DIR
            model_name = config.ML_MODEL_NAME
        except (ImportError, AttributeError):
            model_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "saved_models"
            )
            model_name = "rf_model.pkl"

        model_path = os.path.join(model_dir, model_name)
        meta_path = os.path.join(model_dir, "model_meta.json")

        model_loaded = os.path.exists(model_path)
        meta_available = os.path.exists(meta_path)

        result = {
            "loaded": model_loaded,
            "name": model_name,
            "path": model_path,
        }

        if meta_available:
            try:
                import json
                with open(meta_path) as f:
                    meta = json.load(f)
                result["metrics"] = meta.get("random_forest_metrics", {})
                result["recommended_model"] = meta.get("recommended_model", model_name)
            except Exception:
                pass

        return result

    def _get_resource_usage(self) -> Dict[str, Any]:
        """Get CPU, memory, and disk usage."""
        try:
            import psutil

            # Memory
            mem = psutil.virtual_memory()
            memory = {
                "total_mb": round(mem.total / (1024 * 1024), 1),
                "available_mb": round(mem.available / (1024 * 1024), 1),
                "used_mb": round(mem.used / (1024 * 1024), 1),
                "percent": mem.percent,
            }

            # CPU
            cpu = {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(),
                "count_logical": psutil.cpu_count(logical=True),
            }

            # Disk
            disk = psutil.disk_usage("/")
            disk_info = {
                "total_gb": round(disk.total / (1024 ** 3), 1),
                "used_gb": round(disk.used / (1024 ** 3), 1),
                "free_gb": round(disk.free / (1024 ** 3), 1),
                "percent": disk.percent,
            }

            return {
                "memory": memory,
                "cpu": cpu,
                "disk": disk_info,
            }

        except ImportError:
            logger.warning("psutil not installed — resource monitoring unavailable")
            return {
                "memory": {"error": "psutil not installed"},
                "cpu": {"error": "psutil not installed"},
                "disk": {"error": "psutil not installed"},
            }

    def _get_service_status(self) -> Dict[str, str]:
        """Check status of internal services."""
        services = {}

        # Check prediction service
        try:
            from predict_traffic import TrafficPredictor
            services["prediction"] = "available"
        except ImportError:
            services["prediction"] = "unavailable"

        # Check optimization service
        try:
            from pso_integration import PSOOptimizer
            services["optimization"] = "available"
        except ImportError:
            services["optimization"] = "unavailable"

        # Check database
        try:
            from database import init_db
            services["database"] = "available"
        except ImportError:
            services["database"] = "unavailable"

        # Check Redis (TCP reachability). The redis-py client ignores
        # its socket timeouts across internal retries and can block for
        # 15-50s on Windows when Redis is down, so probe with a raw
        # 1s-timeout socket instead.
        try:
            import socket
            with socket.create_connection(("127.0.0.1", 6379), timeout=1):
                services["cache"] = "available"
        except Exception:
            services["cache"] = "unavailable"

        return services
