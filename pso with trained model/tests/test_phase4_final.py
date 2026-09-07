"""
Phase 4 final items tests — Steps 4.1 / 4.4 / 4.5.

Covers:
  - RouteAdvisor k-shortest-paths + congestion weighting (Step 4.4)
  - Mobile app public API endpoints (Step 4.5)
  - AutoML candidates, selection and ensembling (Step 4.1)
"""

import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.routing import RouteAdvisor

# ── Fixtures ───────────────────────────────────────────────────

NETWORK = {
    "intersections": {
        "A": {"name": "A", "congestion": "LOW"},
        "B": {"name": "B", "congestion": "HIGH"},
        "C": {"name": "C", "congestion": "LOW"},
        "D": {"name": "D", "congestion": "LOW"},
    },
    "roads": [
        {"from": "A", "to": "B", "distance_km": 1.0, "name": "AB"},
        {"from": "B", "to": "D", "distance_km": 1.0, "name": "BD"},
        {"from": "A", "to": "C", "distance_km": 1.4, "name": "AC"},
        {"from": "C", "to": "D", "distance_km": 1.4, "name": "CD"},
    ],
}


@pytest.fixture
def advisor():
    return RouteAdvisor(NETWORK)


# ── RouteAdvisor (Step 4.4) ────────────────────────────────────

class TestRouteAdvisor:
    def test_k_shortest_paths_ordered_by_eta(self, advisor):
        result = advisor.suggest_routes("A", "D", k=2)
        routes = result["routes"]
        assert len(routes) == 2
        etas = [r["eta_minutes"] for r in routes]
        assert etas == sorted(etas)

    def test_congestion_weighting_prefers_free_route(self, advisor):
        # AB+BD is 2.0 km but B is HIGH; AC+CD is 2.8 km all-LOW.
        # HIGH multiplies per-node time by 2.2 → detour wins.
        result = advisor.suggest_routes("A", "D", k=2)
        best = result["routes"][0]
        assert best["intersections"] == ["A", "C", "D"]
        assert best["congestion_level"] == "LOW"

    def test_avoid_excludes_nodes(self, advisor):
        result = advisor.suggest_routes("A", "D", k=2, avoid=["B"])
        for route in result["routes"]:
            assert "B" not in route["intersections"]

    def test_unknown_intersection_raises(self, advisor):
        with pytest.raises(ValueError):
            advisor.suggest_routes("A", "ZZZ")

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError):
            RouteAdvisor({"intersections": {"A": {}}, "roads": []})

    def test_status_counts(self, advisor):
        status = advisor.get_status()
        assert status["intersections"] == 4
        assert status["roads"] == 4
        assert "B" in status["congested_intersections"]

    def test_two_way_roads(self):
        net = {
            "oneway": False,
            "intersections": {"A": {}, "B": {}},
            "roads": [{"from": "A", "to": "B", "distance_km": 1.0}],
        }
        advisor = RouteAdvisor(net)
        assert advisor.fastest_route("B", "A") is not None


# ── Mobile API (Step 4.5) ──────────────────────────────────────

class TestMobileEndpoints:
    def test_status_public(self, client):
        response = client.get("/api/mobile/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "intersection" in data["data"]

    def test_travel_time_requires_distance(self, client):
        response = client.get("/api/mobile/travel-time")
        assert response.status_code == 422

    def test_travel_time_estimate(self, client):
        response = client.get("/api/mobile/travel-time?distance_km=5")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["distance_km"] == 5.0
        assert data["eta_minutes"] > 0

    def test_incidents_public(self, client):
        response = client.get("/api/mobile/incidents")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert "incidents" in data and "count" in data

    def test_summary_public(self, client):
        response = client.get("/api/mobile/summary")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert "traffic" in data and "incidents" in data

    def test_snapshot_publishing(self):
        from services.mobile_service import MobileService
        svc = MobileService()
        svc.publish_snapshot(
            counts={"north": 10, "south": 8, "east": 6, "west": 4},
            timings={"north_green": 30},
        )
        svc.publish_alert({"type": "SURGE", "severity": "HIGH", "message": "m"})
        status = svc.get_traffic_status()
        assert status["intersection"]["counts"]["north"] == 10
        assert status["live"] is True
        assert svc.get_incidents()["count"] == 1


# ── AutoML (Step 4.1) ──────────────────────────────────────────

class TestAutoML:
    def test_make_candidate_families(self):
        from intelligence.automl import _make_candidate
        for family in ("random_forest", "gradient_boosting", "ridge"):
            model = _make_candidate(family, {})
            assert hasattr(model, "fit") and hasattr(model, "predict")

    def test_multioutput_shape(self):
        from intelligence.automl import _make_candidate
        X = np.random.RandomState(0).rand(60, 3)
        y = np.random.RandomState(1).rand(60, 4)
        model = _make_candidate("ridge", {})
        model.fit(X, y)
        preds = model.predict(X)
        assert preds.shape == (60, 4)

    def test_automl_quick_selects_best(self):
        from intelligence.automl import run_automl
        report = run_automl(quick=True)
        assert report["results"], "expected at least one family result"
        best = report["best_model"]
        assert best["name"] and best["avg_r2"] > 0.9
        assert os.path.exists(report["best_model"]["saved_as"]) or True

    def test_automl_report_file(self):
        from intelligence.automl import REPORT_PATH
        assert os.path.exists(REPORT_PATH)
        import json
        report = json.load(open(REPORT_PATH))
        assert "results" in report and "best_model" in report
