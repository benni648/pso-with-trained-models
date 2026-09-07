"""
Vision pipeline unit tests.

Covers the pure-Python parts of the camera pipeline that do not
require OpenCV / ultralytics: zone counting and deriving prediction
input from camera counts.
"""

import pytest

from vision.counter import ZoneCounter

# Simple 1000x800 layout with four quadrant zones
ZONES = {
    "north": [[400, 0], [800, 0], [800, 400], [400, 400]],
    "south": [[400, 400], [800, 400], [800, 800], [400, 800]],
    "east": [[800, 400], [1000, 400], [1000, 800], [800, 800]],
    "west": [[0, 0], [400, 0], [400, 400], [0, 400]],
}


class TestZoneCounter:
    def test_counts_vehicles_in_zone(self):
        """Vehicles whose center falls in a zone are counted there."""
        counter = ZoneCounter(ZONES)
        vehicles = [
            {"track_id": 1, "bbox": [500, 100, 550, 150]},   # north
            {"track_id": 2, "bbox": [600, 500, 650, 550]},   # south
            {"track_id": 3, "bbox": [850, 500, 900, 550]},   # east
            {"track_id": 4, "bbox": [100, 100, 150, 150]},   # west
        ]
        counts = counter.update(vehicles)
        assert counts["north"] == 1
        assert counts["south"] == 1
        assert counts["east"] == 1
        assert counts["west"] == 1
        assert counts["total"] == 4

    def test_vehicle_outside_all_zones_not_counted(self):
        """Vehicles outside every zone should be excluded."""
        counter = ZoneCounter(ZONES)
        vehicles = [{"track_id": 9, "bbox": [2000, 2000, 2100, 2100]}]
        counts = counter.update(vehicles)
        assert counts["total"] == 0

    def test_point_in_polygon_rectangle(self):
        """Ray-casting correctly classifies points inside/outside."""
        rect = [[0, 0], [10, 0], [10, 10], [0, 10]]
        assert ZoneCounter._point_in_polygon((5, 5), rect) is True
        assert ZoneCounter._point_in_polygon((15, 5), rect) is False
        assert ZoneCounter._point_in_polygon((5, -5), rect) is False

    def test_empty_tracked_vehicles(self):
        """Empty input yields zero counts."""
        counter = ZoneCounter(ZONES)
        counts = counter.update([])
        assert counts["total"] == 0


class TestPredictFromCameraCounts:
    def test_derives_prediction_from_counts(self, app):
        """Camera counts produce a valid model prediction."""
        from services.prediction_service import PredictionService
        service = PredictionService()
        if service.predictor is None:
            pytest.skip("Model not available")

        counts = {"north": 12, "south": 8, "east": 15, "west": 6}
        result = service.predict_from_camera_counts(counts)

        for key in ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]:
            assert key in result
            assert result[key] >= 0

    def test_high_volume_derives_high_congestion(self):
        """Large totals map to HIGH congestion for the model input."""
        from services.prediction_service import PredictionService
        service = PredictionService()
        if service.predictor is None:
            pytest.skip("Model not available")

        counts = {"north": 20, "south": 20, "east": 20, "west": 20}
        result = service.predict_from_camera_counts(counts)
        assert result["input_data"]["congestion_level"] == "HIGH"
        assert result["input_data"]["density"] == 1.0

    def test_empty_counts_raise(self):
        """Empty counts should raise a PredictionError."""
        from services.prediction_service import PredictionService
        from utils.errors import PredictionError
        service = PredictionService()
        with pytest.raises(PredictionError):
            service.predict_from_camera_counts({})