"""
=====================================================================
 Event Bridge — Phase 5 (Step 5.1)
=====================================================================
 Bridges the in-process EventBus to external event streaming.

 Design:
   - EventBridge subscribes to every EventType on the EventBus and
     forwards each event dict to all configured backends.
   - Backends are pluggable; failures in a backend never break the
     publisher (they are logged and swallowed).

 Backends:
   LoggingBackend — always available; writes one structured JSON
                    line per event via the standard logger.
   KafkaBackend   — enabled when kafka-python is importable AND
                    KAFKA_ENABLED=true. Publishes JSON to
                    KAFKA_TOPIC on KAFKA_BOOTSTRAP_SERVERS (comma-
                    separated). The client is created lazily and
                    reconnect-safe (rebuilt after send errors).

 The kafka-python package is OPTIONAL: without it, the bridge runs
 in logging-only mode and the application is unaffected.

 Usage (see api/app.py):
     bridge = EventBridge()
     bridge.start()
     ...
     bridge.stop()
=====================================================================
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from events.events import Event, EventBus, EventType
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


# ── BACKENDS ────────────────────────────────────────────────────

class LoggingBackend:
    """Structured JSON log line per event (always enabled)."""

    def __init__(self):
        self.name = "logging"
        self.enabled = True
        self._logger = LoggerManager.get_logger("event_bridge")

    def send(self, payload: Dict[str, Any]) -> bool:
        self._logger.info("EVENT %s", json.dumps(payload, default=str))
        return True

    def close(self) -> None:
        pass


class KafkaBackend:
    """
    Kafka producer backend (optional dependency).

    Enabled only when:
      1. kafka-python is importable
      2. KAFKA_ENABLED env var is "true"
    """

    def __init__(self, bootstrap_servers: Optional[str] = None,
                 topic: Optional[str] = None):
        self.name = "kafka"
        self.bootstrap_servers = (
            bootstrap_servers
            or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        )
        self.topic = topic or os.getenv("KAFKA_TOPIC", "pso.traffic.events")
        self.enabled = (
            os.getenv("KAFKA_ENABLED", "false").strip().lower() == "true"
        )
        self._producer = None
        self._lock = threading.Lock()

        if self.enabled:
            try:
                from kafka import KafkaProducer  # noqa: F401  (availability probe)
                logger.info(
                    "Kafka backend configured: %s → topic '%s'",
                    self.bootstrap_servers, self.topic,
                )
            except ImportError:
                logger.warning(
                    "KAFKA_ENABLED=true but kafka-python is not installed — "
                    "Kafka backend disabled. Install with: pip install kafka-python"
                )
                self.enabled = False

    def _get_producer(self):
        """Lazily create (or recreate after failure) the producer."""
        if self._producer is None:
            from kafka import KafkaProducer
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                retries=3,
            )
        return self._producer

    def send(self, payload: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            try:
                producer = self._get_producer()
                key = str(payload.get("event_type", "unknown")).encode("utf-8")
                producer.send(self.topic, key=key, value=payload)
                return True
            except Exception as e:
                logger.warning("Kafka send failed (%s) — producer reset", e)
                # Drop the broken producer so the next send rebuilds it
                try:
                    if self._producer is not None:
                        self._producer.close(timeout=1)
                except Exception:
                    pass
                self._producer = None
                return False

    def close(self) -> None:
        with self._lock:
            try:
                if self._producer is not None:
                    self._producer.flush(timeout=5)
                    self._producer.close(timeout=5)
            except Exception:
                pass
            self._producer = None


# ── BRIDGE ──────────────────────────────────────────────────────

class EventBridge:
    """
    Subscribes to the EventBus and fans events out to backends.

    Usage:
        bridge = EventBridge()
        bridge.start()      # subscribes
        bridge.publish_event(event)   # manual bridge (also wired into EventBus)
        bridge.stop()       # unsubscribes, flushes backends
    """

    def __init__(self, backends: Optional[List[Any]] = None):
        if backends is None:
            backends = [LoggingBackend(), KafkaBackend()]
        self.backends = [b for b in backends if getattr(b, "enabled", False)]
        self._running = False
        self._lock = threading.Lock()
        self._forwarded = 0
        self._failed = 0

    # ── lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe the bridge to every event type."""
        with self._lock:
            if self._running:
                return
            for event_type in EventType:
                EventBus.subscribe(event_type, self.publish_event)
            self._running = True
            logger.info(
                "EventBridge started (%d backends: %s)",
                len(self.backends),
                ", ".join(b.name for b in self.backends) or "none",
            )

    def stop(self) -> None:
        """Unsubscribe and flush backends."""
        with self._lock:
            if not self._running:
                return
            for event_type in EventType:
                EventBus.unsubscribe(event_type, self.publish_event)
            self._running = False
            for backend in self.backends:
                try:
                    backend.close()
                except Exception:
                    pass
            logger.info("EventBridge stopped")

    @property
    def running(self) -> bool:
        return self._running

    # ── forwarding ────────────────────────────────────────────

    def publish_event(self, event: Any) -> None:
        """
        EventBus handler: accept an Event (or Event-shaped dict) and
        forward it to every backend. Never raises.
        """
        try:
            payload = self._to_payload(event)
            for backend in self.backends:
                try:
                    if backend.send(payload):
                        self._forwarded += 1
                    else:
                        self._failed += 1
                except Exception as e:
                    self._failed += 1
                    logger.warning(
                        "Event backend '%s' failed: %s", backend.name, e
                    )
        except Exception as e:
            logger.warning(f"EventBridge forwarding failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Bridge status for diagnostics endpoints."""
        return {
            "running": self._running,
            "backends": [
                {
                    "name": b.name,
                    "enabled": getattr(b, "enabled", True),
                    **({"topic": b.topic, "servers": b.bootstrap_servers}
                       if b.name == "kafka" else {}),
                }
                for b in self.backends
            ],
            "forwarded": self._forwarded,
            "failed": self._failed,
        }

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _to_payload(event: Any) -> Dict[str, Any]:
        """Normalise Event objects (or dicts) to a JSON-safe dict."""
        if isinstance(event, dict):
            payload = dict(event)
        elif hasattr(event, "to_dict"):
            payload = event.to_dict()
        else:
            payload = {
                "event_type": str(getattr(event, "event_type", "unknown")),
                "data": getattr(event, "data", {}),
                "timestamp": datetime.utcnow().isoformat(),
            }
        payload.setdefault(
            "bridged_at", datetime.utcnow().isoformat()
        )
        return payload
