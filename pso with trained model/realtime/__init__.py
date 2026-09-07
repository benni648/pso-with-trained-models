"""
=====================================================================
 Realtime Package — WebSocket Live Dashboard
=====================================================================
 Pushes live traffic data to browser clients over WebSocket
 (flask-socketio) without page refreshes.

   socket_manager.py → SocketManager (server → client event emission)
   data_stream.py    → DataStream (background publisher thread)

 The package degrades gracefully: if flask-socketio is not installed
 or the eventlet async worker is unavailable, the rest of the
 application continues to work normally (HTTP polling still applies).
=====================================================================
"""

from realtime.socket_manager import SocketManager
from realtime.data_stream import DataStream

__all__ = ["SocketManager", "DataStream"]