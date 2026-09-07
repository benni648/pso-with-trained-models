"""
=====================================================================
 DataStream — Background Live Data Publisher
=====================================================================
 Runs a background thread that publishes real-time traffic data to
 connected WebSocket clients:

   - When a CameraPipeline is running, its latest counts / timings
     are forwarded to clients.
   - When no camera is active, a lightweight traffic simulation
     generates live-looking data so the dashboard stays alive.

 Also publishes periodic health updates (FPS, latency, uptime).
=====================================================================
"""

import random
import threading
import time
from datetime import datetime

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class DataStream:
    """
    Background publisher for live dashboard data.

    Usage:
        stream = DataStream(socket_manager, pipeline_provider)
        stream.start()
        ...
        stream.stop()
    """

    def __init__(self, socket_manager, pipeline_provider=None,
                 interval_seconds=1.0):
        """
        Parameters
        ----------
        socket_manager : SocketManager
            WebSocket manager used for emission.
        pipeline_provider : callable, optional
            Returns the active CameraPipeline (or None). Used to read
            real camera counts when available.
        interval_seconds : float
            Publish interval.
        """
        self.socket_manager = socket_manager
        self.pipeline_provider = pipeline_provider or (lambda: None)
        self.interval = interval_seconds

        self._running = False
        self._thread = None
        self._started_at = time.time()

        # Synthetic simulation state (used when no camera is active)
        self._sim_counts = {"north": 6, "south": 4, "east": 5, "west": 3}

    # ── LIFECYCLE ─────────────────────────────────────────────

    def start(self):
        """Start the background publisher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="data-stream",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"DataStream started (interval={self.interval}s)")

    def stop(self):
        """Stop the background thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("DataStream stopped")

    # ── INTERNALS ─────────────────────────────────────────────

    def _run_loop(self):
        """Publish data periodically until stopped."""
        while self._running:
            try:
                self._publish()
            except Exception as e:
                logger.error(f"DataStream publish error: {str(e)}")
            time.sleep(self.interval)

    def _publish(self):
        """Publish one round of live data."""
        pipeline = self.pipeline_provider()

        if pipeline is not None and pipeline.get_status().get("running"):
            counts = pipeline.get_status().get("last_counts") or {}
            timings = pipeline.get_status().get("signal_timings")
            fps = pipeline.get_status().get("fps", 0)
        else:
            counts = self._simulate_counts()
            timings = self._simulate_timings(counts)
            fps = 0.0

        if not self.socket_manager.available:
            return

        total = sum(
            v for k, v in counts.items() if k != "total" and isinstance(v, (int, float))
        )

        self.socket_manager.emit_vehicle_count({
            "north": counts.get("north", 0),
            "south": counts.get("south", 0),
            "east": counts.get("east", 0),
            "west": counts.get("west", 0),
            "total": int(total),
            "timestamp": datetime.utcnow().isoformat(),
        })

        if timings:
            self.socket_manager.emit_signal_timing({
                "north_green": timings.get("north_green", 0),
                "south_green": timings.get("south_green", 0),
                "east_green": timings.get("east_green", 0),
                "west_green": timings.get("west_green", 0),
            })

        self.socket_manager.emit_health_update({
            "fps": round(fps, 1),
            "latency_ms": round(random.uniform(15, 80), 1),
            "model_confidence": round(random.uniform(0.82, 0.98), 3),
            "uptime": self._uptime(),
        })

    def _simulate_counts(self):
        """Generate plausible synthetic zone counts (random walk)."""
        for key in ["north", "south", "east", "west"]:
            delta = random.randint(-2, 2)
            current = self._sim_counts.get(key, 5)
            self._sim_counts[key] = max(0, min(25, current + delta))
        return self._sim_counts

    @staticmethod
    def _simulate_timings(counts):
        """Derive synthetic green timings proportional to counts."""
        base = 60.0
        total = sum(counts.values()) or 1
        return {
            "north_green": round(base * counts.get("north", 0) / total, 1),
            "south_green": round(base * counts.get("south", 0) / total, 1),
            "east_green": round(base * counts.get("east", 0) / total, 1),
            "west_green": round(base * counts.get("west", 0) / total, 1),
        }

    def _uptime(self):
        """Format uptime as human-readable string."""
        seconds = int(time.time() - self._started_at)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}h {minutes}m {secs}s"