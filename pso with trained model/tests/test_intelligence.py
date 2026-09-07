"""
Phase 4 intelligence module tests.

Covers anomaly detection, traffic forecasting, multi-intersection
coordination (global PSO / green wave / emergency), the signal
controller client with fallback behavior, and the city TMC client
with webhook notifications.
"""

import http.server
import json
import threading

import pytest

from intelligence.anomaly import AnomalyDetector
from intelligence.forecaster import TrafficForecaster
from intelligence.coordinator import IntersectionCoordinator
from intelligence.controller import SignalControllerClient
from intelligence.tmc import TrafficManagementCenterClient

DIRECTIONS = ["north", "south", "east", "west"]


def _counts(n=5, s=4, e=3, w=2):
    return {"north": n, "south": s, "east": e, "west": w}


class TestAnomalyDetector:
    def test_no_alerts_on_steady_traffic(self):
        detector = AnomalyDetector(window=10)
        for _ in range(10):
            detector.update(_counts())
        alerts = detector.update(_counts())
        assert alerts == []

    def test_surge_detected(self):
        detector = AnomalyDetector(window=15)
        for _ in range(12):
            detector.update(_counts())
        alerts = detector.update(_counts(n=80, s=4, e=3, w=2))
        types = [a["type"] for a in alerts]
        assert "SURGE" in types

    def test_sensor_failure_detected(self):
        detector = AnomalyDetector()
        alerts = detector.update(_counts(n=-5))
        assert any(a["type"] == "SENSOR_FAILURE" for a in alerts)

        # NaN on a different direction is a new episode
        alerts = detector.update(_counts(e=float("nan")))
        assert any(a["type"] == "SENSOR_FAILURE" for a in alerts)

    def test_road_closure_after_zeros(self):
        detector = AnomalyDetector(window=10, closure_min_zeros=3)
        for _ in range(8):
            detector.update(_counts(n=10))
        alerts = []
        for _ in range(3):
            alerts += detector.update(_counts(n=0))
        assert any(a["type"] == "ROAD_CLOSURE" for a in alerts)

    def test_sudden_drop_detected(self):
        detector = AnomalyDetector(window=15)
        for _ in range(12):
            detector.update(_counts(n=60, s=4, e=3, w=2))
        alerts = detector.update(_counts(n=1, s=4, e=3, w=2))
        assert any(a["type"] == "ACCIDENT" for a in alerts)

    def test_analyze_window_flags_outliers(self):
        detector = AnomalyDetector()
        series = {
            "north": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 40.0],
            "south": [3.0] * 9,
        }
        markers = detector.analyze_window(series)
        assert any(m["direction"] == "north" and m["type"] == "SURGE" for m in markers)

    def test_isolation_forest_returns_structure(self):
        detector = AnomalyDetector(window=25)
        for i in range(25):
            detector.update(_counts(n=5 + i % 5))
        result = detector.isolation_forest_anomaly()
        assert result["used_isolation_forest"] is True
        assert "score" in result and "is_anomaly" in result


class TestTrafficForecaster:
    def test_forecast_grows_with_rising_trend(self):
        forecaster = TrafficForecaster()
        for i in range(20):
            forecaster.observe(_counts(n=10 + i, s=5 + i, e=4, w=3))
        result = forecaster.forecast_next(steps=3)
        assert len(result["steps"]) == 3
        # Rising history → rising forecast
        north_forecast = [s["north_vehicles"] for s in result["steps"]]
        assert north_forecast[0] > 20
        assert north_forecast[-1] > north_forecast[0]

    def test_congestion_horizons_levels(self):
        forecaster = TrafficForecaster()
        for i in range(30):
            forecaster.observe(_counts(n=8 + i, s=6 + i, e=5 + i, w=4 + i))
        horizons = forecaster.predict_congestion()["horizons"]
        assert set(horizons.keys()) == {"5", "10", "15"}
        # Heavy traffic → HIGH at every horizon
        for h in horizons.values():
            assert h["level"] == "HIGH"

    def test_congestion_low_for_quiet_traffic(self):
        forecaster = TrafficForecaster()
        for _ in range(20):
            forecaster.observe(_counts(n=2, s=2, e=1, w=1))
        horizons = forecaster.predict_congestion()["horizons"]
        for h in horizons.values():
            assert h["level"] == "LOW"

    def test_insufficient_history_is_safe(self):
        forecaster = TrafficForecaster()
        result = forecaster.forecast_next(steps=2)
        assert result["steps"][0]["total"] == 0.0


class TestIntersectionCoordinator:
    DEMANDS = {
        "INT_001": _counts(n=18, s=6, e=4, w=5),
        "INT_002": _counts(n=4, s=9, e=12, w=3),
    }

    def test_global_optimization_within_bounds(self):
        coordinator = IntersectionCoordinator(n_particles=25, n_iterations=25)
        result = coordinator.optimize(self.DEMANDS)
        for iid, entry in result["intersections"].items():
            for key in ["north_green", "south_green", "east_green", "west_green"]:
                assert 5 <= entry[key] <= 60, f"{iid} {key} out of bounds"
        assert result["global_fitness"] > 0
        assert result["n_intersections"] == 2

    def test_emergency_preemption_holds_approach_green(self):
        coordinator = IntersectionCoordinator(n_particles=25, n_iterations=25)
        result = coordinator.optimize(
            self.DEMANDS,
            emergency={"intersection_id": "INT_001",
                       "directions": ["north"],
                       "duration": 30},
        )
        emergency = result["emergency"]
        assert emergency["active"] is True
        assert emergency["intersection_id"] == "INT_001"
        assert result["intersections"]["INT_001"]["north_green"] == 60.0

    def test_green_wave_offsets_stagger(self):
        coordinator = IntersectionCoordinator()
        result = coordinator.optimize(self.DEMANDS, arterial=["INT_001", "INT_002"])
        wave = result["green_wave"]
        assert wave["enabled"] is True
        assert len(wave["offsets"]) == 2
        assert wave["offsets"]["INT_002"] > wave["offsets"]["INT_001"]

    def test_busy_intersection_gets_more_green(self):
        """Heavy north demand on INT_001 → longer north green than quiet east."""
        coordinator = IntersectionCoordinator(n_particles=30, n_iterations=30)
        result = coordinator.optimize(self.DEMANDS)
        t1 = result["intersections"]["INT_001"]
        assert t1["north_green"] > t1["east_green"]


class TestSignalControllerClient:
    def test_no_url_simulates(self):
        client = SignalControllerClient(url=None)
        result = client.apply_timings("INT_001", _counts(n=10))
        assert result["applied"] is True
        assert result["simulated"] is True
        assert result["fallback"] is False

    def test_unreachable_controller_falls_back(self):
        client = SignalControllerClient(url="http://127.0.0.1:1", timeout=1.0)
        result = client.apply_timings("INT_001", _counts(n=10))
        assert result["applied"] is True
        assert result["fallback"] is True
        assert result["timings"]["north_green"] == 20.0
        assert client.get_status()["fallback_active"] is True

    def test_reachable_controller_applies(self):
        received = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                received["body"] = json.loads(self.rfile.read(length))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = SignalControllerClient(url=f"http://127.0.0.1:{port}", timeout=2.0)
            timings = {"north_green": 10, "south_green": 12,
                       "east_green": 8, "west_green": 9}
            result = client.apply_timings("INT_001", timings, override=True)
            assert result["applied"] is True
            assert result["fallback"] is False
            assert received["body"]["intersection_id"] == "INT_001"
            assert received["body"]["override"] is True
            assert received["body"]["timings"]["north_green"] == 10
        finally:
            server.shutdown()


class TestIntelligenceService:
    def test_service_observe_and_check(self):
        from services.intelligence_service import IntelligenceService
        service = IntelligenceService()
        assert service.available is True
        for _ in range(12):
            service.observe_counts(_counts())
        result = service.check_anomalies(_counts(n=80))
        assert result["count"] >= 1

    def test_service_optimize_requires_demands(self):
        from services.intelligence_service import IntelligenceService
        from utils.errors import TrafficAPIError
        service = IntelligenceService()
        with pytest.raises(TrafficAPIError):
            service.optimize_intersections({})

    def test_service_tmc_status(self):
        from services.intelligence_service import IntelligenceService
        service = IntelligenceService()
        status = service.tmc_status()
        assert "configured_url" in status
        assert status["webhook_count"] >= 0


class TestTrafficManagementCenterClient:
    def test_no_url_disabled(self):
        client = TrafficManagementCenterClient(url=None, webhook_urls=[])
        result = client.push_traffic_data("INT_001", _counts(n=10))
        assert result["sent"] is False
        assert result["disabled"] is True
        assert client.notify({"type": "ANOMALY"}) == []

    def test_unreachable_tmc_reports_failure(self):
        client = TrafficManagementCenterClient(
            url="http://127.0.0.1:1", timeout=1.0, webhook_urls=[]
        )
        result = client.push_traffic_data("INT_001", _counts(n=10))
        assert result["sent"] is False
        assert result["disabled"] is False
        assert result["status"] is None

    def test_reachable_tmc_receives_data(self):
        received = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                received["body"] = json.loads(self.rfile.read(length))
                received["api_key"] = self.headers.get("X-API-Key")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = TrafficManagementCenterClient(
                url=f"http://127.0.0.1:{port}",
                api_key="secret-key",
                webhook_urls=[],
                timeout=2.0,
            )
            result = client.push_traffic_data(
                "INT_001", _counts(n=12), timings={"north_green": 30}
            )
            assert result["sent"] is True
            assert result["status"] == 200
            assert received["body"]["intersection_id"] == "INT_001"
            assert received["body"]["counts"]["north"] == 12
            assert received["api_key"] == "secret-key"
        finally:
            server.shutdown()

    def test_webhook_notifications_delivered(self):
        deliveries = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                deliveries.append(json.loads(self.rfile.read(length)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            webhook = f"http://127.0.0.1:{port}/hook"
            client = TrafficManagementCenterClient(
                url=None, webhook_urls=[webhook], timeout=2.0
            )
            results = client.notify({
                "type": "ANOMALY", "severity": "HIGH", "message": "surge"
            })
            assert len(results) == 1
            assert results[0]["delivered"] is True
            assert deliveries[0]["type"] == "ANOMALY"
            assert "notified_at" in deliveries[0]
        finally:
            server.shutdown()

    def test_webhook_failure_is_reported_not_raised(self):
        client = TrafficManagementCenterClient(
            url=None,
            webhook_urls=["http://127.0.0.1:1/hook"],
            timeout=1.0,
        )
        results = client.notify({"type": "TEST"})
        assert len(results) == 1
        assert results[0]["delivered"] is False
        assert results[0]["status"] is None
        assert client.get_status()["last_notifications"] == results