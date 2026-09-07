"""
=====================================================================
 Signal Controller Client — Phase 4 (Step 4.5)
=====================================================================
 Sends optimized signal timings to a real traffic-light controller
 over REST, with the mandated behavior on connection loss:

   - On success          → {"applied": True,  "fallback": False}
   - On connection loss  → logs the failure, applies FIXED timings as
                           a safe fallback → {"applied": True,
                                              "fallback": True}
   - No URL configured   → simulated/local controller → simulated mode

 The controller endpoint is configurable via the CONTROLLER_URL
 environment variable (see .env.example). Uses only the Python
 standard library (urllib), so no extra dependency is required.
=====================================================================
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

DEFAULT_FALLBACK_TIMINGS = {
    "north_green": 20.0,
    "south_green": 20.0,
    "east_green": 20.0,
    "west_green": 20.0,
}

DIRECTION_KEYS = ["north_green", "south_green", "east_green", "west_green"]


class SignalControllerClient:
    """
    REST client for traffic signal controllers with safe fallback.

    Usage:
        controller = SignalControllerClient(url="http://controller:8080")
        result = controller.apply_timings("INT_001", {...timings})
    """

    def __init__(self, url: Optional[str] = None,
                 fallback_timings: Optional[Dict[str, float]] = None,
                 timeout: float = 3.0):
        """
        Parameters
        ----------
        url : str, optional
            Base URL of the controller API. Defaults to the
            CONTROLLER_URL env var; None/empty → simulated mode.
        fallback_timings : dict, optional
            Fixed timings used when the controller is unreachable.
        timeout : float
            HTTP timeout in seconds.
        """
        self.url = url or os.getenv("CONTROLLER_URL", "").strip() or None
        self.fallback_timings = {
            k: fallback_timings.get(k, v)
            for k, v in DEFAULT_FALLBACK_TIMINGS.items()
        } if fallback_timings else dict(DEFAULT_FALLBACK_TIMINGS)
        self.timeout = timeout

        self.last_apply: Optional[Dict[str, Any]] = None
        self.fallback_active = False
        self._started_at = time.time()

    # ── PUBLIC API ─────────────────────────────────────────────

    def apply_timings(self, intersection_id: str, timings: Dict[str, float],
                      override: bool = False) -> Dict[str, Any]:
        """
        Send signal timings to the controller.

        Parameters
        ----------
        intersection_id : str
            Target intersection.
        timings : dict
            {north_green, south_green, east_green, west_green}.
        override : bool
            Mark this as an emergency/preemption application.

        Returns
        -------
        dict
            {"applied": bool, "fallback": bool, "simulated": bool,
             "timings": {...}, ...}
        """
        payload = {
            "intersection_id": intersection_id,
            "timings": self._clean_timings(timings),
            "override": bool(override),
            "sent_at": datetime.utcnow().isoformat(),
        }

        # Simulated mode — no physical controller configured
        if not self.url:
            result = {
                "applied": True,
                "fallback": False,
                "simulated": True,
                "intersection_id": intersection_id,
                "timings": payload["timings"],
                "message": "No controller URL configured — applied to simulated controller",
            }
            self.last_apply = result
            self.fallback_active = False
            return result

        try:
            req = urllib.request.Request(
                f"{self.url.rstrip('/')}/timings",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
            result = {
                "applied": status < 400,
                "fallback": False,
                "simulated": False,
                "intersection_id": intersection_id,
                "timings": payload["timings"],
                "controller_status": status,
            }
            logger.info(
                f"Timings applied to controller {intersection_id} "
                f"(status {status}, override={override})"
            )

        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, ValueError) as e:
            # Connection loss → safe fixed-timing fallback
            self.fallback_active = True
            fallback = {
                "north_green": self.fallback_timings["north_green"],
                "south_green": self.fallback_timings["south_green"],
                "east_green": self.fallback_timings["east_green"],
                "west_green": self.fallback_timings["west_green"],
            }
            result = {
                "applied": True,
                "fallback": True,
                "simulated": False,
                "intersection_id": intersection_id,
                "timings": fallback,
                "controller_status": None,
                "reason": f"Controller unreachable ({e.__class__.__name__}) — "
                          "using fixed fallback timings",
            }
            logger.error(
                f"Controller {intersection_id} unreachable: {str(e)} — "
                f"fixed fallback timings applied"
            )

        self.last_apply = result
        return result

    def emergency_override(self, intersection_id: str,
                           directions: list) -> Dict[str, Any]:
        """
        Apply an emergency preemption: hold the given approaches at
        maximum green (60s) and cross-streets at minimum.

        Parameters
        ----------
        intersection_id : str
        directions : list[str]
            Approaches to hold green, e.g. ["north"].

        Returns
        -------
        dict
            Result of apply_timings with override=True.
        """
        dir_map = {"north": "north_green", "south": "south_green",
                   "east": "east_green", "west": "west_green"}
        selected = [dir_map[d.lower()] for d in directions
                    if d.lower() in dir_map]
        if not selected:
            raise ValueError("No valid directions provided for override")

        timings = dict(DEFAULT_FALLBACK_TIMINGS)
        for key in DIRECTION_KEYS:
            timings[key] = 5.0  # cross streets red
        for key in selected:
            timings[key] = 60.0  # emergency approach green
        return self.apply_timings(intersection_id, timings, override=True)

    def get_status(self) -> Dict[str, Any]:
        """Client configuration and last application result."""
        return {
            "configured_url": self.url or "none (simulated)",
            "fallback_active": self.fallback_active,
            "fallback_timings": self.fallback_timings,
            "last_apply": self.last_apply,
            "uptime_s": round(time.time() - self._started_at, 1),
        }

    # ── HELPERS ───────────────────────────────────────────────

    @staticmethod
    def _clean_timings(timings: Dict[str, float]) -> Dict[str, float]:
        """Normalise and clamp timing values."""
        cleaned = {}
        for key in DIRECTION_KEYS:
            raw = timings.get(key, 20.0)
            try:
                cleaned[key] = round(min(120.0, max(1.0, float(raw))), 1)
            except (TypeError, ValueError):
                cleaned[key] = 20.0
        return cleaned