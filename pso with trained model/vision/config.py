"""
=====================================================================
 Camera & Detection Configuration
=====================================================================
 Single-intersection defaults for the real-time vision pipeline.

 Change the camera ``source`` to your actual feed:
   - IP camera:  "rtsp://user:pass@192.168.1.100:554/stream1"
   - USB webcam: 0  (or 1, 2, ...)
   - Video file: "path/to/video.mp4"

 Zone polygons are in image coordinates (x, y) and should be drawn
 over your camera's field of view so each polygon covers one
 approach lane of the intersection.
=====================================================================
"""

CAMERA_CONFIG = {
    "intersection_id": "INT_001",
    "cameras": [
        {
            "id": "cam_north",
            "source": "rtsp://192.168.1.100:554/stream1",
            "position": "north",
            "resolution": [1920, 1080],
        }
    ],
    # Directional zones as polygons [[x1,y1], [x2,y2], ...]
    "zones": {
        "north": [[400, 100], [600, 100], [600, 300], [400, 300]],
        "south": [[400, 500], [600, 500], [600, 700], [400, 700]],
        "east":  [[700, 300], [900, 300], [900, 500], [700, 500]],
        "west":  [[100, 300], [300, 300], [300, 500], [100, 500]],
    },
    "detection": {
        "model": "yolov8n.pt",       # yolov8n (fast, CPU) → yolov8m/x (accurate, GPU)
        "confidence": 0.5,
        # COCO classes: car(2), motorcycle(3), bus(5), truck(7)
        "vehicle_classes": [2, 3, 5, 7],
    },
    "tracking": {
        "max_age": 30,
        "n_init": 3,
    },
    "processing": {
        "interval_seconds": 1.0,     # how often to process a frame
        "fps_limit": 10,             # cap stream read rate
    },
}