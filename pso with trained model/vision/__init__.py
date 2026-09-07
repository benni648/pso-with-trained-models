"""
=====================================================================
 Vision Package — Real-Time Camera Pipeline
=====================================================================
 Detects vehicles from camera feeds (YOLOv8), tracks them (DeepSORT),
 counts them per direction (zone counter), and feeds the counts into
 the ML predictor + PSO optimizer.

 Components:
   stream.py    → VideoStream (RTSP / USB / file sources)
   detector.py  → VehicleDetector (YOLOv8, vehicle classes only)
   tracker.py   → VehicleTracker (DeepSORT multi-object tracking)
   counter.py   → ZoneCounter (per-direction polygon counting)
   config.py    → CAMERA_CONFIG (single-intersection defaults)
   pipeline.py  → CameraPipeline (orchestrates the full loop)

 Note: heavy dependencies (opencv-python, ultralytics, torch,
 deep-sort-realtime) are imported lazily so the rest of the
 application can start without them.
=====================================================================
"""

from vision.config import CAMERA_CONFIG
from vision.counter import ZoneCounter
from vision.stream import VideoStream

__all__ = [
    "CAMERA_CONFIG",
    "ZoneCounter",
    "VideoStream",
    "VehicleDetector",
    "VehicleTracker",
    "CameraPipeline",
]

# Detector / tracker / pipeline are optional imports (heavy deps)
def __getattr__(name):
    if name == "VehicleDetector":
        from vision.detector import VehicleDetector
        return VehicleDetector
    if name == "VehicleTracker":
        from vision.tracker import VehicleTracker
        return VehicleTracker
    if name == "CameraPipeline":
        from vision.pipeline import CameraPipeline
        return CameraPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")