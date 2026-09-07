"""
=====================================================================
 VideoStream — Camera Source Reader
=====================================================================
 Reads frames from RTSP streams, USB webcams, or video files in a
 background thread. Always serves the *latest* frame (old frames are
 dropped) so downstream processing never blocks on I/O.

 Features:
   - Auto-reconnect on stream failure
   - Latest-frame semantics (no unbounded queue)
   - Configurable FPS cap
   - Graceful stop / resource release

 Requires: opencv-python (cv2) — imported lazily.
=====================================================================
"""

import threading
import time

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class VideoStream:
    """
    Background camera reader with auto-reconnect.

    Usage:
        stream = VideoStream("rtsp://...", name="cam_north")
        stream.start()
        frame = stream.read()      # None until first frame arrives
        stream.stop()
    """

    def __init__(self, source, name="camera_1", fps_limit=None):
        """
        Parameters
        ----------
        source : str or int
            RTSP URL ("rtsp://..."), video file path, or webcam index (0).
        name : str
            Logical name for logging (e.g., "cam_north").
        fps_limit : float, optional
            Maximum read rate in frames per second (None = unlimited).
        """
        self.source = source
        self.name = name
        self.fps_limit = fps_limit

        self._capture = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread = None
        self._fps = 0.0
        self._frame_count = 0
        self._last_read_time = 0.0
        self._reconnect_delay = 2.0  # seconds between reconnect attempts
        self._error = None

    # ── LIFECYCLE ─────────────────────────────────────────────

    def start(self):
        """Start reading frames in a background thread."""
        if self._running:
            return

        import cv2  # lazy import

        self._running = True
        self._capture = self._open_capture(cv2)
        self._thread = threading.Thread(
            target=self._read_loop,
            name=f"video-stream-{self.name}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"VideoStream '{self.name}' started (source={self.source})")

    def stop(self):
        """Stop the reader and release camera resources."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._release_capture()
        logger.info(f"VideoStream '{self.name}' stopped")

    # ── PUBLIC API ────────────────────────────────────────────

    def read(self):
        """
        Return the latest frame (BGR numpy array) or None.

        Never blocks; returns the most recent frame available.
        """
        with self._frame_lock:
            return self._frame

    def get_fps(self):
        """Current measured frame rate."""
        return self._fps

    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_error(self):
        return self._error

    # ── INTERNALS ─────────────────────────────────────────────

    def _open_capture(self, cv2):
        """Open the capture device based on source type."""
        if isinstance(self.source, int):
            capture = cv2.VideoCapture(self.source)
        else:
            capture = cv2.VideoCapture(self.source)
        return capture

    def _read_loop(self):
        """Background loop: read frames, cap FPS, auto-reconnect."""
        import cv2  # lazy import

        min_interval = 1.0 / self.fps_limit if self.fps_limit else 0.0

        while self._running:
            loop_start = time.time()

            try:
                ok, frame = self._capture.read()
                if not ok or frame is None:
                    self._error = "Stream read failed — reconnecting"
                    logger.warning(
                        f"VideoStream '{self.name}': {self._error}"
                    )
                    self._reconnect(cv2)
                    time.sleep(self._reconnect_delay)
                    continue

                self._error = None
                with self._frame_lock:
                    self._frame = frame

                now = time.time()
                if self._last_read_time:
                    elapsed = now - self._last_read_time
                    if elapsed > 0:
                        self._fps = 0.9 * self._fps + 0.1 * (1.0 / elapsed)
                self._last_read_time = now
                self._frame_count += 1

            except Exception as e:
                self._error = str(e)
                logger.error(f"VideoStream '{self.name}' error: {str(e)}")
                self._reconnect(cv2)
                time.sleep(self._reconnect_delay)

            # FPS capping
            if min_interval:
                elapsed = time.time() - loop_start
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)

    def _reconnect(self, cv2):
        """Release and reopen the capture device."""
        self._release_capture()
        time.sleep(0.5)
        try:
            self._capture = self._open_capture(cv2)
        except Exception as e:
            self._error = f"Reconnect failed: {str(e)}"

    def _release_capture(self):
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None