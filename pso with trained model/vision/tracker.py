"""
=====================================================================
 VehicleTracker — Multi-Object Tracking
=====================================================================
 Assigns stable track IDs to detected vehicles across frames so each
 vehicle is counted only once and can be followed through occlusion.

 Two tracking modes:

   1. DeepSORT (appearance-based) — used when an ``embedder`` is
      configured (e.g. "mobilenet", "torchreid"). Requires the
      deep-sort-realtime package plus the embedder's backend.

   2. IoU association (default, motion-only) — a lightweight greedy
      frame-to-frame matcher based on bounding-box overlap. Needs no
      extra dependencies and is sufficient for per-direction counting.

 The embedder is never required: DeepSORT's own embedder=None mode
 demands per-detection embeddings (which a bare YOLO detector does not
 produce), so we only call DeepSORT when an embedder is provided and
 otherwise use the IoU fallback.

 Usage:
     tracker = VehicleTracker(max_age=30, n_init=3)
     tracked = tracker.update(detections, frame)
     # [{"track_id": 1, "bbox": [x1,y1,x2,y2], "class": "car",
     #   "age": 15, "confidence": 0.87}, ...]
=====================================================================
"""

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# Minimum IoU for a detection to continue an existing track
IOU_MATCH_THRESHOLD = 0.2


class VehicleTracker:
    """
    Tracks vehicles across frames.

    Uses DeepSORT when an appearance embedder is configured, otherwise
    falls back to greedy IoU association between consecutive frames.
    """

    def __init__(self, max_age=30, n_init=3, embedder=None):
        """
        Parameters
        ----------
        max_age : int
            Frames to keep a track after it stops being detected
            (used by the DeepSORT mode).
        n_init : int
            Detections required before a DeepSORT track is confirmed.
        embedder : str, optional
            Appearance embedder ("mobilenet", "torchreid", ...).
            Defaults to None → IoU (motion-only) association.
        """
        self.max_age = max_age
        self.n_init = n_init
        self.embedder = embedder

        self.tracker = None
        self.mode = "iou"  # or "deepsort"
        self._prev_tracks = []  # for IoU mode: [{track_id, bbox}]
        self._next_track_id = 1
        self._last_detections = []

        if embedder is not None:
            self._load_deepsort()

    # ── SETUP ─────────────────────────────────────────────────

    def _load_deepsort(self):
        """Initialize DeepSORT with an appearance embedder."""
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
        except ImportError as e:
            logger.warning(
                "deep-sort-realtime not installed — falling back to "
                "IoU tracking. Install with: pip install deep-sort-realtime"
            )
            self.embedder = None
            return

        try:
            self.tracker = DeepSort(
                max_age=self.max_age,
                n_init=self.n_init,
                embedder=self.embedder,
            )
            self.mode = "deepsort"
            logger.info(
                f"VehicleTracker in DeepSORT mode (embedder={self.embedder})"
            )
        except Exception as e:
            logger.warning(
                f"DeepSORT init with embedder={self.embedder} failed "
                f"({str(e)}) — falling back to IoU tracking"
            )
            self.embedder = None
            self.tracker = None

    # ── PUBLIC API ────────────────────────────────────────────

    def update(self, detections, frame=None):
        """
        Update tracks with the latest detections.

        Parameters
        ----------
        detections : list[dict]
            Output of VehicleDetector.detect(): each with bbox, class,
            class_id, confidence.
        frame : numpy.ndarray, optional
            Current frame (required for DeepSORT appearance crops).

        Returns
        -------
        list[dict]
            Active tracks: [{"track_id", "bbox", "class", "age",
                             "confidence"}, ...]
        """
        self._last_detections = detections

        if self.mode == "deepsort" and self.tracker is not None:
            return self._update_deepsort(detections, frame)

        return self._update_iou(detections)

    def get_active_tracks(self):
        """Return the tracks from the most recent update."""
        if self.mode == "deepsort" and self.tracker is not None:
            tracks = self.tracker.tracker.tracks
            return [
                {
                    "track_id": int(t.track_id),
                    "bbox": [float(v) for v in t.to_ltrb()],
                    "class": self._class_name(t.det_class),
                    "age": int(t.age),
                }
                for t in tracks
                if t.is_confirmed()
            ]
        return list(self._prev_tracks)

    # ── DeepSORT MODE ─────────────────────────────────────────

    def _update_deepsort(self, detections, frame):
        """Associate detections via DeepSORT."""
        sort_detections = []
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            sort_detections.append([
                x1, y1, x2, y2,
                det.get("confidence", 1.0),
                det.get("class_id", 0),
            ])

        tracks = self.tracker.update_tracks(sort_detections, frame=frame)

        tracked = []
        for track in tracks:
            if not track.is_confirmed() and track.time_since_update > 1:
                continue

            ltrb = track.to_ltrb()  # [left, top, right, bottom]
            tracked.append({
                "track_id": int(track.track_id),
                "bbox": [float(ltrb[0]), float(ltrb[1]),
                         float(ltrb[2]), float(ltrb[3])],
                "class": self._class_name(track.det_class),
                "age": int(track.age),
                "confidence": float(track.det_conf) if track.det_conf else 0.0,
            })

        self._prev_tracks = [
            {k: t[k] for k in ("track_id", "bbox")} for t in tracked
        ]
        return tracked

    # ── IoU FALLBACK MODE ─────────────────────────────────────

    def _update_iou(self, detections):
        """
        Greedy IoU association between previous tracks and detections.

        Each detection is matched to the previous track with the
        highest IoU (above IOU_MATCH_THRESHOLD); unmatched detections
        start new tracks. This is motion-only and stateless across
        gaps (no coasting), which is sufficient for zone counting.
        """
        if not detections:
            self._prev_tracks = []
            return []

        prev = list(self._prev_tracks)
        matched_prev = set()
        tracked = []

        for det in detections:
            bbox = [float(v) for v in det["bbox"]]
            best_iou = 0.0
            best_idx = -1

            for i, track in enumerate(prev):
                if i in matched_prev:
                    continue
                iou = self._iou(bbox, track["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = i

            if best_idx >= 0 and best_iou >= IOU_MATCH_THRESHOLD:
                matched_prev.add(best_idx)
                track_id = prev[best_idx]["track_id"]
            else:
                track_id = self._next_track_id
                self._next_track_id += 1

            tracked.append({
                "track_id": track_id,
                "bbox": bbox,
                "class": det.get("class", "vehicle"),
                "age": 1,
                "confidence": float(det.get("confidence", 1.0)),
            })

        self._prev_tracks = [
            {k: t[k] for k in ("track_id", "bbox")} for t in tracked
        ]
        return tracked

    # ── HELPERS ───────────────────────────────────────────────

    @staticmethod
    def _iou(box_a, box_b):
        """
        Intersection-over-union of two [x1, y1, x2, y2] boxes.

        Returns
        -------
        float
            IoU in [0, 1].
        """
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        if inter == 0.0:
            return 0.0

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _class_name(class_id):
        """Map a COCO class id to a human-readable name."""
        try:
            from vision.detector import VEHICLE_CLASS_NAMES
            return VEHICLE_CLASS_NAMES.get(int(class_id), f"class_{class_id}")
        except ImportError:
            return f"class_{class_id}"