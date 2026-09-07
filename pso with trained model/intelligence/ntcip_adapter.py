"""
=====================================================================
 NTCIP-Style Controller Adapter — Phase 5 (Step 5.3)
=====================================================================
 Translates the system's per-direction green timings into NTCIP
 1202-style phase objects so a standards-compliant field controller
 (or its REST/SNPP gateway) can consume them.

 Phase assignment follows the common NEMA dual-ring convention used
 with NTCIP 1202 Actuated Signal Controllers:

   Ring 1:  Phase 2 = North approach  (NB)
            Phase 4 = East approach   (EB)
   Ring 2:  Phase 6 = South approach  (SB)
            Phase 8 = West approach   (WB)

 (Phases 1/3/5/7 are the opposing protected movements; the simple
 four-approach mapping treats each approach as one phase.)

 Behavior:
   - CONTROLLER_PROTOCOL unset/"rest"  → plain SignalControllerClient
   - CONTROLLER_PROTOCOL="ntcip"       → NTCIPAdapter: converts the
     timings dict into per-phase green times, then either POSTs the
     phase table to {CONTROLLER_URL}/phases (gateway mode) or falls
     back to the REST client's behavior (including the mandated
     fixed-timing fallback on connection loss).

 Only the standard library is used (urllib), mirroring the other
 intelligence clients.
=====================================================================
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# Approach → (NTCIP phase number, NEMA movement label)
PHASE_MAP = {
    "north_green": {"phase": 2, "movement": "NB"},
    "east_green": {"phase": 4, "movement": "EB"},
    "south_green": {"phase": 6, "movement": "SB"},
    "west_green": {"phase": 8, "movement": "WB"},
}

DIRECTION_KEYS = list(PHASE_MAP.keys())

# NTCIP 1202 maxGreen / minGreen sanity bounds (seconds)
MIN_GREEN = 1.0
MAX_GREEN = 120.0


class NTCIPAdapter:
    """
    NTCIP 1202-style phase adapter.

    Usage:
        adapter = NTCIPAdapter(url="http://gateway:8080")
        result = adapter.apply_phase_timings("INT_001", timings)
    """

    def __init__(self, url: Optional[str] = None,
                 timeout: float = 3.0,
                 fallback_client=None):
        """
        Parameters
        ----------
        url : str, optional
            Gateway base URL (defaults to CONTROLLER_URL).
        timeout : float
            HTTP timeout in seconds.
        fallback_client : optional
            A SignalControllerClient-like object used for the
            fixed-timing fallback when the gateway is unreachable.
        """
        self.url = (url or os.getenv("CONTROLLER_URL", "").strip()) or None
        self.timeout = timeout
        self._fallback = fallback_client
        self.last_apply: Optional[Dict[str, Any]] = None

    # ── TRANSLATION ────────────────────────────────────────────

    @staticmethod
    def to_phase_table(timings: Dict[str, Any],
                       intersection_id: str = "",
                       override: bool = False) -> List[Dict[str, Any]]:
        """
        Convert {north_green: N, ...} to an NTCIP-style phase table.

        Returns a list of phase objects:
            [{"phase": 2, "movement": "NB", "minGreen": 5.0,
              "maxGreen": N, "green": N, "yellow": 3.0,
              "allRed": 1.0, "enabled": true}, ...]
        """
        table: List[Dict[str, Any]] = []
        for key, meta in PHASE_MAP.items():
            try:
                green = float(timings.get(key, 20.0))
            except (TypeError, ValueError):
                green = 20.0
            green = round(min(MAX_GREEN, max(MIN_GREEN, green)), 1)
            table.append({
                "phase": meta["phase"],
                "movement": meta["movement"],
                "minGreen": min(5.0, green),
                "maxGreen": green,
                "green": green,
                "yellow": 3.0,   # NTCIP-typical yellow interval
                "allRed": 1.0,   # NTCIP-typical all-red clearance
                "enabled": True,
                "pedOverride": bool(override),
            })
        table.sort(key=lambda p: p["phase"])
        return table

    @staticmethod
    def from_phase_table(table: List[Dict[str, Any]]) -> Dict[str, float]:
        """Inverse of to_phase_table (phase number → direction key)."""
        reverse = {meta["phase"]: key for key, meta in PHASE_MAP.items()}
        timings: Dict[str, float] = {}
        for entry in table or []:
            phase = entry.get("phase")
            key = reverse.get(phase)
            if key:
                try:
                    timings[key] = float(entry.get("green", 20.0))
                except (TypeError, ValueError):
                    timings[key] = 20.0
        return timings

    # ── APPLICATION ────────────────────────────────────────────

    def apply_phase_timings(self, intersection_id: str,
                            timings: Dict[str, Any],
                            override: bool = False) -> Dict[str, Any]:
        """
        Translate and push the phase table to the gateway.

        Returns a result dict compatible with
        SignalControllerClient.apply_timings (applied / fallback /
        protocol fields) so the API layer can treat both uniformly.
        """
        phase_table = self.to_phase_table(timings, intersection_id, override)
        payload = {
            "intersection_id": intersection_id,
            "protocol": "NTCIP-1202",
            "phases": phase_table,
            "override": bool(override),
            "sent_at": _utc_now_iso(),
        }

        if not self.url:
            result = {
                "applied": True,
                "fallback": False,
                "simulated": True,
                "protocol": "ntcip",
                "intersection_id": intersection_id,
                "phases": phase_table,
                "message": "No controller URL configured — NTCIP phase table simulated",
            }
            self.last_apply = result
            return result

        try:
            req = urllib.request.Request(
                f"{self.url.rstrip('/')}/phases",
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
                "protocol": "ntcip",
                "intersection_id": intersection_id,
                "phases": phase_table,
                "controller_status": status,
            }
            logger.info(
                "NTCIP phase table applied to %s (status %s, override=%s)",
                intersection_id, status, override,
            )
        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, ValueError) as e:
            # Connection loss → delegate to the safe fixed fallback
            logger.error(
                "NTCIP gateway %s unreachable: %s — using fallback client",
                intersection_id, e,
            )
            result = {
                "applied": True,
                "fallback": True,
                "simulated": False,
                "protocol": "ntcip",
                "intersection_id": intersection_id,
                "phases": phase_table,
                "controller_status": None,
                "reason": f"NTCIP gateway unreachable ({e.__class__.__name__}) "
                          "— fixed fallback timings applied",
            }
            if self._fallback is not None:
                try:
                    fb = self._fallback.apply_timings(
                        intersection_id, timings, override=override
                    )
                    result["fallback_detail"] = fb.get("timings")
                except Exception as fe:
                    logger.warning(f"Fallback client failed: {fe}")

        self.last_apply = result
        return result

    def get_status(self) -> Dict[str, Any]:
        """Adapter status for diagnostics endpoints."""
        return {
            "protocol": "ntcip",
            "configured_url": self.url or "none (simulated)",
            "phase_map": {
                key: meta["phase"] for key, meta in PHASE_MAP.items()
            },
            "last_apply": self.last_apply,
        }


def _utc_now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()
