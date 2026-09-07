"""
=====================================================================
 CameraPipeline — Real-Time Vision Orchestrator
=====================================================================
 Chains the full real-time flow:

     stream → detector → tracker → counter → prediction → optimization

 Runs in a background thread at a configurable interval and pushes
 results to an optional callback (e.g., a WebSocket emitter).

 Usage:
     from vision.pipeline import CameraPipeline
     from vision.config import CAMERA_CONFIG

     def on_results(data):
         print(data["counts"], data["signal_timings"])

     pipeline = CameraPipeline(
         CAMERA_CONFIG,
         prediction_service=prediction_service,
         optimization_service=optimization_service,
         emit_callback=on_results,
     )
     pipeline.start()
     ...
     pipeline.stop()
=====================================================================
"""

import threading
import time

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class CameraPipeline:
    """
    Orchestrates camera capture, detection, tracking, counting,
    prediction, and optimization in a background loop.
    """

    def __init__(self, camera_config, prediction_service=None,
                 optimization_service=None, emit_callback=None,
                 interval_seconds=None):
        """
        Parameters
        ----------
        camera_config : dict
            Configuration from vision.config.CAMERA_CONFIG.
        prediction_service : PredictionService, optional
            Used to predict next-step counts from zone counts.
        optimization_service : OptimizationService, optional
            Used to compute signal timings from predictions.
        emit_callback : callable, optional
            Called with a results dict after each processed frame.
        interval_seconds : float, optional
            Processing interval; defaults to config value.
        """
        from vision.stream import VideoStream
        from vision.detector import VehicleDetector
        from vision.tracker import VehicleTracker
        from vision.counter import ZoneCounter

        self.config = camera_config
        self.intersection_id = camera_config.get("intersection_id", "INT_001")
        self.prediction_service = prediction_service
        self.optimization_service = optimization_service
        self.emit_callback = emit_callback

        processing = camera_config.get("processing", {})
        self.interval = interval_seconds or processing.get("interval_seconds", 1.0)

        detection_cfg = camera_config.get("detection", {})
        tracking_cfg = camera_config.get("tracking", {})

        # Primary camera source
        cameras = camera_config.get("cameras", [])
        if not cameras:
            raise ValueError("camera_config must define at least one camera")
        self.camera = cameras[0]

        # Build components (may raise RuntimeError if vision deps missing)
        self.stream = VideoStream(
            self.camera["source"],
            name=self.camera.get("id", "camera_1"),
            fps_limit=processing.get("fps_limit"),
        )
        self.detector = VehicleDetector(
            model_size=detection_cfg.get("model", "yolov8n.pt"),
            confidence=detection_cfg.get("confidence", 0.5),
            vehicle_classes=detection_cfg.get("vehicle_classes"),
        )
        self.tracker = VehicleTracker(
            max_age=tracking_cfg.get("max_age", 30),
            n_init=tracking_cfg.get("n_init", 3),
        )
        self.counter = ZoneCounter(camera_config.get("zones", {}))

        # Runtime state
        self._running = False
        self._thread = None
        self._last_counts = {}
        self._last_prediction = None
        self._last_timings = None
        self._last_frame_at = None
        self._processed_frames = 0
        self._error = None

        logger.info(
            f"CameraPipeline '{self.intersection_id}' initialized "
            f"(source={self.camera['source']}, interval={self.interval}s)"
        )

    # ── LIFECYCLE ─────────────────────────────────────────────

    def start(self):
        """Start the background processing loop."""
        if self._running:
            return

        self.stream.start()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"camera-pipeline-{self.intersection_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"CameraPipeline '{self.intersection_id}' started")

    def stop(self):
        """Stop the background loop and release resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.stream.stop()
        logger.info(f"CameraPipeline '{self.intersection_id}' stopped")

    # ── PUBLIC API ────────────────────────────────────────────

    def process_frame(self):
        """
        Process a single frame synchronously: detect, track, count,
        then (optionally) predict and optimize.

        Returns
        -------
        dict
            Results: {"counts", "prediction", "signal_timings",
                      "detections", "fitness", "timestamp"}
        """
        frame = self.stream.read()
        if frame is None:
            return {"counts": {}, "timestamp": time.time()}

        detections = self.detector.detect(frame)
        tracked = self.tracker.update(detections, frame)
        counts = self.counter.update(tracked)

        result = {
            "intersection_id": self.intersection_id,
            "counts": counts,
            "detections": detections,
            "tracked": tracked,
            "timestamp": time.time(),
        }

        # Optional: prediction + optimization on the zone counts
        if self.prediction_service and self._has_counts(counts):
            prediction = self.prediction_service.predict_from_camera_counts(counts)
            result["prediction"] = prediction

            if self.optimization_service:
                try:
                    optimization = self.optimization_service.optimize(prediction)
                    result["signal_timings"] = {
                        k: v for k, v in optimization.items() if k != "fitness"
                    }
                    result["fitness"] = optimization.get("fitness", 0)
                except Exception as e:
                    self._error = f"Optimization failed: {str(e)}"
                    logger.error(self._error)

        self._last_counts = counts
        self._last_prediction = result.get("prediction")
        self._last_timings = result.get("signal_timings")
        self._last_frame_at = time.time()
        self._processed_frames += 1
        self._error = None

        return result

    def get_status(self):
        """
        Current pipeline status.

        Returns
        -------
        dict
            {"running", "fps", "processed_frames", "last_counts",
             "last_prediction", "signal_timings", "error"}
        """
        return {
            "running": self._running,
            "intersection_id": self.intersection_id,
            "source": self.camera["source"],
            "fps": round(self.stream.get_fps(), 2),
            "processed_frames": self._processed_frames,
            "last_counts": self._last_counts,
            "last_prediction": self._last_prediction,
            "signal_timings": self._last_timings,
            "error": self._error or self.stream.get_error(),
        }

    def get_annotated_frame(self):
        """
        Get the latest frame with zone overlays drawn.

        Returns
        -------
        numpy.ndarray or None
            Annotated BGR frame (zones only; detection boxes require
            a detect_with_annotations pass).
        """
        frame = self.stream.read()
        if frame is None:
            return None
        return self.counter.draw_zones(frame)

    # ── INTERNALS ─────────────────────────────────────────────

    def _run_loop(self):
        """Background loop: process frames at a fixed interval."""
        while self._running:
            start = time.time()

            try:
                result = self.process_frame()
                if self.emit_callback and callable(self.emit_callback):
                    self.emit_callback(result)
            except Exception as e:
                self._error = str(e)
                logger.error(
                    f"CameraPipeline '{self.intersection_id}' iteration error: {str(e)}"
                )

            elapsed = time.time() - start
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)

    @staticmethod
    def _has_counts(counts):
        """True if the counts dict has any numeric zone values."""
        return any(
            isinstance(v, (int, float)) and v > 0
            for k, v in counts.items() if k != "total"
        )