"""
=====================================================================
 SocketManager — WebSocket Event Management
=====================================================================
 Thin wrapper around flask-socketio providing:

   Server → Client events:
     "vehicle_count"    — {north, south, east, west, total, timestamp}
     "signal_timing"    — {north_green, south_green, east_green, west_green}
     "health_update"    — {fps, latency_ms, model_confidence, uptime}
     "alert"            — {type, message, severity}

   Client → Server events:
     "subscribe"        — {intersection_id} join a room
     "unsubscribe"      — {intersection_id} leave a room
     "request_frame"    — request current annotated frame

 All methods are safe no-ops when flask-socketio is unavailable,
 so the app keeps running without WebSocket support.
=====================================================================
"""

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class SocketManager:
    """
    Manages the Socket.IO instance and event handlers.

    Usage:
        manager = SocketManager()
        available = manager.init_app(app)
        if available:
            manager.emit_vehicle_count({"north": 12, "south": 8, ...})
    """

    def __init__(self):
        self.socketio = None
        self.available = False
        self.last_frame = None

    # ── SETUP ─────────────────────────────────────────────────

    def init_app(self, app):
        """
        Initialize Socket.IO with the Flask app.

        Parameters
        ----------
        app : Flask
            The Flask application instance.

        Returns
        -------
        bool
            True if WebSocket support is active.
        """
        try:
            from flask_socketio import SocketIO
        except ImportError:
            logger.warning(
                "flask-socketio not installed — WebSocket live updates disabled. "
                "Install with: pip install flask-socketio"
            )
            self.available = False
            return False

        try:
            self.socketio = SocketIO(app, cors_allowed_origins="*")
            self._register_handlers()
            self.available = True
            logger.info("Socket.IO initialized — WebSocket live updates enabled")
        except Exception as e:
            logger.warning(f"Socket.IO initialization failed: {str(e)}")
            self.available = False

        return self.available

    def run(self, app, host="0.0.0.0", port=5000, debug=False):
        """Run the Flask app with Socket.IO support (if available)."""
        if self.available and self.socketio is not None:
            self.socketio.run(app, host=host, port=port, debug=debug)
        else:
            app.run(host=host, port=port, debug=debug)

    # ── EVENT HANDLERS (client → server) ──────────────────────

    def _register_handlers(self):
        """Register Socket.IO event handlers."""

        @self.socketio.on("subscribe")
        def on_subscribe(data):
            intersection_id = (data or {}).get("intersection_id", "default")
            from flask_socketio import join_room
            join_room(intersection_id)
            logger.info(f"Client subscribed to room: {intersection_id}")

        @self.socketio.on("unsubscribe")
        def on_unsubscribe(data):
            intersection_id = (data or {}).get("intersection_id", "default")
            from flask_socketio import leave_room
            leave_room(intersection_id)
            logger.info(f"Client left room: {intersection_id}")

        @self.socketio.on("request_frame")
        def on_request_frame():
            if self.last_frame is not None and self.socketio is not None:
                self.socketio.emit("detection_frame", self.last_frame)

    # ── EMITTERS (server → client) ────────────────────────────

    def emit_vehicle_count(self, data, room=None):
        """Emit live vehicle counts per direction."""
        self._emit("vehicle_count", data, room)

    def emit_signal_timing(self, data, room=None):
        """Emit optimized green-light timings."""
        self._emit("signal_timing", data, room)

    def emit_detection_frame(self, base64_frame, room=None):
        """Emit a base64-encoded annotated frame."""
        self.last_frame = base64_frame
        self._emit("detection_frame", {"frame": base64_frame}, room)

    def emit_health_update(self, data, room=None):
        """Emit FPS / latency / confidence health metrics."""
        self._emit("health_update", data, room)

    def emit_alert(self, data, room=None):
        """Emit an alert (accident, congestion spike, sensor failure)."""
        self._emit("alert", data, room)

    def emit_pipeline_result(self, result):
        """
        Publish a full CameraPipeline result to all clients.

        Parameters
        ----------
        result : dict
            Output of CameraPipeline.process_frame().
        """
        counts = result.get("counts") or {}
        signal_timings = result.get("signal_timings")

        if counts:
            self.emit_vehicle_count({
                "north": counts.get("north", 0),
                "south": counts.get("south", 0),
                "east": counts.get("east", 0),
                "west": counts.get("west", 0),
                "total": counts.get("total", 0),
                "timestamp": result.get("timestamp"),
            })

        if signal_timings:
            self.emit_signal_timing({
                "north_green": signal_timings.get("north_green", 0),
                "south_green": signal_timings.get("south_green", 0),
                "east_green": signal_timings.get("east_green", 0),
                "west_green": signal_timings.get("west_green", 0),
            })

    # ── INTERNALS ─────────────────────────────────────────────

    def _emit(self, event, data, room=None):
        """Emit an event to a room (or globally) if available."""
        if not self.available or self.socketio is None:
            return
        try:
            if room:
                self.socketio.emit(event, data, room=room)
            else:
                self.socketio.emit(event, data)
        except Exception as e:
            logger.debug(f"Socket emit failed ({event}): {str(e)}")