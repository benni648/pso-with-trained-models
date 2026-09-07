"""
=====================================================================
 VehicleDetector — YOLOv8 Vehicle Detection
=====================================================================
 Runs YOLOv8 inference on camera frames and returns only vehicle
 detections (car, motorcycle, bus, truck).

 Requires: ultralytics (+ torch) — imported lazily.

 Usage:
     detector = VehicleDetector(model_size="yolov8n.pt", confidence=0.5)
     detections = detector.detect(frame)
     # [{"bbox": [x1, y1, x2, y2], "class": "car",
     #   "class_id": 2, "confidence": 0.87}, ...]
=====================================================================
"""

import numpy as np

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# COCO class names relevant to traffic
VEHICLE_CLASS_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Default COCO vehicle class IDs
DEFAULT_VEHICLE_CLASSES = [2, 3, 5, 7]


class VehicleDetector:
    """
    YOLOv8-based vehicle detector filtered to vehicle classes.

    The ultralytics package is imported lazily so importing this
    module does not require torch to be installed.
    """

    def __init__(self, model_size="yolov8n.pt", confidence=0.5,
                 vehicle_classes=None, device=None):
        """
        Parameters
        ----------
        model_size : str
            YOLOv8 model file (yolov8n.pt fast → yolov8x.pt accurate).
        confidence : float
            Minimum detection confidence (0-1).
        vehicle_classes : list[int], optional
            COCO class IDs to keep (default: car, motorcycle, bus, truck).
        device : str, optional
            Inference device, e.g. "cpu", "cuda:0" (None = auto).
        """
        self.model_size = model_size
        self.confidence = confidence
        self.vehicle_classes = vehicle_classes or DEFAULT_VEHICLE_CLASSES
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the YOLOv8 model (lazy import of ultralytics)."""
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise RuntimeError(
                "VehicleDetector requires 'ultralytics'. "
                "Install with: pip install ultralytics"
            ) from e

        try:
            self.model = YOLO(self.model_size)
            if self.device:
                self.model.to(self.device)
            logger.info(
                f"VehicleDetector loaded: {self.model_size} "
                f"(confidence={self.confidence}, classes={self.vehicle_classes})"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load YOLO model '{self.model_size}': {str(e)}. "
                "The model file is downloaded on first use — check network access."
            ) from e

    def detect(self, frame):
        """
        Detect vehicles in a frame.

        Parameters
        ----------
        frame : numpy.ndarray
            BGR image from the camera.

        Returns
        -------
        list[dict]
            Detections: [{"bbox": [x1,y1,x2,y2], "class": "car",
                          "class_id": 2, "confidence": 0.87}, ...]
        """
        if frame is None:
            return []

        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            classes=self.vehicle_classes,
            verbose=False,
        )

        detections = []
        if not results:
            return detections

        boxes = results[0].boxes
        if boxes is None:
            return detections

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)

        for bbox, conf, cls_id in zip(xyxy, confs, cls_ids):
            detections.append({
                "bbox": [float(bbox[0]), float(bbox[1]),
                         float(bbox[2]), float(bbox[3])],
                "class": VEHICLE_CLASS_NAMES.get(int(cls_id), f"class_{cls_id}"),
                "class_id": int(cls_id),
                "confidence": float(conf),
            })

        return detections

    def detect_with_annotations(self, frame):
        """
        Detect vehicles and return an annotated copy of the frame
        with bounding boxes and labels drawn.

        Parameters
        ----------
        frame : numpy.ndarray
            BGR image.

        Returns
        -------
        tuple
            (detections, annotated_frame)
        """
        detections = self.detect(frame)
        annotated = frame.copy() if frame is not None else None

        if annotated is None:
            return detections, None

        try:
            import cv2
        except ImportError:
            return detections, annotated

        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            label = f"{det['class']} {det['confidence']:.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated, label, (x1, max(0, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )

        return detections, annotated