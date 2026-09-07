"""
Phase 5 tests — Scale, Integration & Client Experience.

Covers:
  - EventBridge forwarding + status (Step 5.1)
  - NTCIP adapter translation + fallback behavior (Step 5.3)
  - Model lifecycle task wiring (Step 5.4)
  - New API endpoints: /mobile, /api/events/status,
    /api/models/retrain (Steps 5.4/5.5)
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from events.events import Event, EventType, EventBus


# ── Step 5.1: Event bridge ─────────────────────────────────────

class _RecorderBackend:
    name = "recorder"
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        return True

    def close(self):
        pass


class _FailingBackend:
    name = "failing"
    enabled = True

    def send(self, payload):
        raise RuntimeError("boom")

    def close(self):
        pass


class TestEventBridge:
    def test_forwarding_to_backends(self):
        from workers.event_bridge import EventBridge
        rec = _RecorderBackend()
        bridge = EventBridge(backends=[rec])
        bridge.start()
        try:
            EventBus.publish(Event(EventType.ANOMALY_DETECTED, {"type": "SURGE"}))
            EventBus.publish(Event(EventType.FORECAST_CREATED, {"steps": 3}))
            payloads = rec.sent
            assert len(payloads) == 2
            assert {p["event_type"] for p in payloads} == {
                EventType.ANOMALY_DETECTED.value,
                EventType.FORECAST_CREATED.value,
            }
            assert all("bridged_at" in p for p in payloads)
        finally:
            bridge.stop()
        assert bridge.running is False

    def test_backend_failure_does_not_break_bridge(self):
        from workers.event_bridge import EventBridge
        rec = _RecorderBackend()
        bridge = EventBridge(backends=[_FailingBackend(), rec])
        bridge.start()
        try:
            EventBus.publish(Event(EventType.MODEL_RETRAINED, {"r2": 0.95}))
            assert len(rec.sent) == 1
            status = bridge.get_status()
            assert status["failed"] >= 1
            assert status["forwarded"] >= 1
        finally:
            bridge.stop()

    def test_kafka_backend_disabled_by_default(self):
        from workers.event_bridge import KafkaBackend
        backend = KafkaBackend()
        assert backend.enabled is False or os.getenv("KAFKA_ENABLED") == "true"

    def test_bridge_status_shape(self):
        from workers.event_bridge import EventBridge
        bridge = EventBridge(backends=[_RecorderBackend()])
        status = bridge.get_status()
        assert status["running"] is False
        assert status["backends"][0]["name"] == "recorder"


# ── Step 5.3: NTCIP adapter ────────────────────────────────────

class TestNTCIPAdapter:
    def test_phase_table_translation(self):
        from intelligence.ntcip_adapter import NTCIPAdapter
        table = NTCIPAdapter.to_phase_table({
            "north_green": 42, "south_green": 38,
            "east_green": 30, "west_green": 25,
        })
        phases = {p["phase"]: p for p in table}
        assert phases[2]["movement"] == "NB"
        assert phases[2]["green"] == 42.0
        assert phases[6]["green"] == 38.0
        assert all(p["yellow"] == 3.0 for p in table)
        assert [p["phase"] for p in table] == sorted(p["phase"] for p in table)

    def test_phase_clamping(self):
        from intelligence.ntcip_adapter import NTCIPAdapter
        table = NTCIPAdapter.to_phase_table({"north_green": 500, "south_green": -5})
        by_phase = {p["phase"]: p for p in table}
        assert by_phase[2]["green"] == 120.0
        assert by_phase[6]["green"] == 1.0

    def test_roundtrip_translation(self):
        from intelligence.ntcip_adapter import NTCIPAdapter
        original = {"north_green": 40, "south_green": 35,
                    "east_green": 30, "west_green": 20}
        table = NTCIPAdapter.to_phase_table(original)
        back = NTCIPAdapter.from_phase_table(table)
        assert back == original

    def test_simulated_mode_without_url(self):
        from intelligence.ntcip_adapter import NTCIPAdapter
        adapter = NTCIPAdapter(url=None)
        result = adapter.apply_phase_timings("INT_001", {"north_green": 30})
        assert result["applied"] is True
        assert result["simulated"] is True
        assert result["protocol"] == "ntcip"
        assert len(result["phases"]) == 4

    def test_unreachable_gateway_falls_back(self):
        from intelligence.ntcip_adapter import NTCIPAdapter
        from intelligence.controller import SignalControllerClient

        class _FB(SignalControllerClient):
            def __init__(self):
                self.applied = None

            def apply_timings(self, intersection_id, timings, override=False):
                self.applied = (intersection_id, timings)
                return {"applied": True, "fallback": True, "timings": timings}

        fb = _FB()
        adapter = NTCIPAdapter(url="http://127.0.0.1:1", timeout=1.0,
                               fallback_client=fb)
        result = adapter.apply_phase_timings("INT_001", {"north_green": 33})
        assert result["fallback"] is True
        assert result["reason"]
        assert fb.applied[0] == "INT_001"

    def test_service_uses_rest_by_default(self):
        from services.intelligence_service import IntelligenceService
        service = IntelligenceService()
        assert service.available is True
        assert getattr(service, "ntcip", None) is None
        status = service.controller_status()
        assert status["protocol"] == "rest"

    def test_service_ntcip_selection(self, monkeypatch):
        monkeypatch.setenv("CONTROLLER_PROTOCOL", "ntcip")
        from services.intelligence_service import IntelligenceService
        service = IntelligenceService()
        assert service.ntcip is not None
        result = service.apply_controller_timings(
            "INT_001", {"north_green": 25, "south_green": 25,
                        "east_green": 25, "west_green": 25}
        )
        assert result["protocol"] == "ntcip"
        assert result["simulated"] is True


# ── Step 5.4: Model lifecycle ──────────────────────────────────

class TestModelLifecycle:
    def test_task_registry(self):
        import workers.tasks.model_tasks  # noqa: F401  (register tasks)
        from workers.celery_app import app as celery_app
        assert "workers.tasks.model_tasks.nightly_retrain_task" in celery_app.tasks
        assert "workers.tasks.model_tasks.retrain_model_task" in celery_app.tasks

    def test_beat_schedule_includes_retrain(self):
        from workers.celery_app import app as celery_app
        assert "nightly-model-retrain" in celery_app.conf.beat_schedule

    def test_retrain_helper_runs_quick(self, monkeypatch):
        # Avoid a full AutoML run: patch run_automl to a stub.
        import workers.tasks.model_tasks as mt
        import intelligence.automl
        from intelligence.automl import REPORT_PATH, BEST_MODEL_PATH

        def _stub(quick=False):
            return {"best_model": {"name": "ridge", "avg_r2": 0.95},
                    "results": [], "elapsed_s": 0.1}

        monkeypatch.setattr(intelligence.automl, "run_automl", _stub)
        result = mt._run_retrain(quick=True)
        assert result["best_model"]["name"] == "ridge"
        assert result["report_path"] == REPORT_PATH
        assert result["model_path"] == BEST_MODEL_PATH


# ── API endpoints ──────────────────────────────────────────────

class TestPhase5Endpoints:
    def test_mobile_page_served(self, client):
        response = client.get("/mobile")
        assert response.status_code == 200

    def test_events_status_requires_admin(self, client, viewer_token):
        response = client.get("/api/events/status", headers={
            "Authorization": f"Bearer {viewer_token}",
        })
        assert response.status_code == 403

    def test_events_status_admin(self, client, admin_token):
        response = client.get("/api/events/status", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert "backends" in data and "running" in data

    def test_retrain_requires_auth(self, client):
        response = client.post("/api/models/retrain", json={"quick": True})
        assert response.status_code == 401

    def test_retrain_quick_synchronous(self, client, admin_token, monkeypatch):
        # Celery broker is unavailable in tests → synchronous fallback;
        # stub run_automl so the test stays fast.
        def _stub(quick=False):
            return {"best_model": {"name": "stub", "avg_r2": 0.9},
                    "results": []}

        import intelligence.automl
        monkeypatch.setattr(intelligence.automl, "run_automl", _stub)
        response = client.post("/api/models/retrain",
                               headers={"Authorization": f"Bearer {admin_token}"},
                               json={"quick": True})
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["mode"] in ("synchronous", "queued")
