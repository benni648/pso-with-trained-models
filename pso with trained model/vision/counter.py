"""
=====================================================================
 ZoneCounter — Per-Direction Vehicle Counting
=====================================================================
 Counts tracked vehicles inside directional polygon zones
 (north / south / east / west) using point-in-polygon checks on each
 vehicle's center point.

 Pure-Python ray-casting is used for the counting logic (no OpenCV
 required); OpenCV is only used for drawing zone overlays.

 Usage:
     counter = ZoneCounter(zones_config)
     counts = counter.update(tracked_vehicles)
     # {"north": 12, "south": 8, "east": 15, "west": 6, "total": 41}
=====================================================================
"""

import numpy as np

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class ZoneCounter:
    """
    Counts vehicles per directional zone.

    Parameters
    ----------
    zones_config : dict
        {"north": [[x1,y1],[x2,y2],...], "south": [...], "east": [...], "west": [...]}
        Each value is a polygon (list of [x, y] vertices).
    """

    def __init__(self, zones_config):
        self.zones = zones_config or {}
        self.zone_names = list(self.zones.keys())
        self.counts = {name: 0 for name in self.zone_names}
        logger.info(
            f"ZoneCounter initialized with zones: {self.zone_names}"
        )

    def update(self, tracked_vehicles):
        """
        Count tracked vehicles per zone.

        Parameters
        ----------
        tracked_vehicles : list[dict]
            Output of VehicleTracker.update(): each with bbox, track_id, ...

        Returns
        -------
        dict
            {"north": n, "south": n, "east": n, "west": n, "total": n}
        """
        self.counts = {name: 0 for name in self.zone_names}

        for vehicle in tracked_vehicles:
            bbox = vehicle.get("bbox")
            if not bbox:
                continue

            center = self._center(bbox)
            zone = self._locate(center)
            if zone:
                self.counts[zone] += 1

        self.counts["total"] = sum(
            self.counts[name] for name in self.zone_names
        )
        return dict(self.counts)

    def draw_zones(self, frame):
        """
        Draw zone polygons on a frame for visualization.

        Parameters
        ----------
        frame : numpy.ndarray
            BGR image.

        Returns
        -------
        numpy.ndarray
            Frame with zone polygons drawn.
        """
        if frame is None:
            return frame

        try:
            import cv2
        except ImportError:
            return frame

        annotated = frame.copy()
        for name, polygon in self.zones.items():
            pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [pts], isClosed=True, color=(255, 0, 0), thickness=2)
            # Label the zone at its centroid
            cx = int(np.mean([p[0] for p in polygon]))
            cy = int(np.mean([p[1] for p in polygon]))
            cv2.putText(
                annotated, name.upper(), (cx, cy),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2,
            )

        return annotated

    # ── INTERNALS ─────────────────────────────────────────────

    @staticmethod
    def _center(bbox):
        """Compute the center point of a bounding box."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _locate(self, point):
        """
        Find which zone contains the point.

        Returns
        -------
        str or None
            Zone name, or None if the point is not in any zone.
        """
        for name, polygon in self.zones.items():
            if self._point_in_polygon(point, polygon):
                return name
        return None

    @staticmethod
    def _point_in_polygon(point, polygon):
        """
        Ray-casting point-in-polygon test.

        Parameters
        ----------
        point : tuple
            (x, y).
        polygon : list
            List of [x, y] vertices.

        Returns
        -------
        bool
            True if the point is inside the polygon.
        """
        x, y = point
        n = len(polygon)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            ):
                inside = not inside
            j = i

        return inside