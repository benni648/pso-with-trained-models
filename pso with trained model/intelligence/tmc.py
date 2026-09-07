"""
=====================================================================
 City Traffic Management Center (TMC) Client — Phase 4 (Step 4.5)
=====================================================================
 Integrates with an existing city Traffic Management Center over
 REST (SCADA gateway style), mirroring SignalControllerClient:

   - Data exchange   → push_traffic_data() posts zone counts /
                       signal timings to {TMC_URL}/data
   - Notifications   → notify() delivers alert payloads (anomalies,
                       controller fallback, preemption) to every
                       webhook URL listed in TMC_WEBHOOK_URLS
                       (comma-separated), POST {webhook} as JSON
   - Graceful no-op  → when TMC_URL / webhooks are not configured
                       the client reports "disabled" and succeeds
                       without network calls

 Configuration (environment variables, see .env.example):
   TMC_URL           base URL of the TMC gateway (optional)
   TMC_API_KEY       sent as X-API-Key header on every request
   TMC_WEBHOOK_URLS  comma-separated webhook endpoints

 Uses only the Python standard library (urllib) — no extra runtime
 dependency is required.
=====================================================================
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class TrafficManagementCenterClient:
    """
    REST + webhook client for a city Traffic Management Center.

    Usage:
        tmc = TrafficManagementCenterClient()
        tmc.push_traffic_data("INT_001", counts, timings)
        results = tmc.notify({"type": "ANOMALY", "message": "..."})
    """

    def __init__(self, url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 webhook_urls: Optional[List[str]] = None,
                 timeout: float = 3.0):
        """
        Parameters
        ----------
        url : str, optional
            Base URL of the TMC gateway. Defaults to the TMC_URL
            env var; None/empty → disabled (no data exchange).
        api_key : str, optional
            Sent as X-API-Key header. Defaults to TMC_API_KEY env var.
        webhook_urls : list[str], optional
            Defaults to the comma-separated TMC_WEBHOOK_URLS env var.
        timeout : float
            HTTP timeout in seconds per request.
        """
        self.url = (url or os.getenv("TMC_URL", "").strip()) or None
        self.api_key = (api_key or os.getenv("TMC_API_KEY", "").strip()) or None

        if webhook_urls is None:
            raw = os.getenv("TMC_WEBHOOK_URLS", "")
            webhook_urls = [u.strip() for u in raw.split(",") if u.strip()]
        self.webhook_urls = webhook_urls

        self.timeout = timeout
        self.last_push: Optional[Dict[str, Any]] = None
        self.last_notifications: List[Dict[str, Any]] = []
        self._started_at = time.time()

    # ── PUBLIC API ─────────────────────────────────────────────

    def push_traffic_data(self, intersection_id: str,
                          counts: Optional[Dict[str, Any]] = None,
                          timings: Optional[Dict[str, Any]] = None,
                          extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Push a traffic data sample to the TMC gateway.

        Parameters
        ----------
        intersection_id : str
            Source intersection identifier.
        counts : dict, optional
            Per-direction vehicle counts {north, south, east, west}.
        timings : dict, optional
            Current/optimized signal timings.
        extra : dict, optional
            Additional fields merged into the payload.

        Returns
        -------
        dict
            {"sent": bool, "disabled": bool, "status": int|None, ...}
        """
        payload = {
            "intersection_id": intersection_id,
            "counts": counts or {},
            "timings": timings or {},
            "sent_at": datetime.utcnow().isoformat(),
        }
        if extra:
            payload.update(extra)

        if not self.url:
            result = {
                "sent": False,
                "disabled": True,
                "reason": "TMC_URL not configured — data exchange disabled",
                "payload": payload,
            }
            self.last_push = result
            return result

        try:
            status, _ = self._post_json(f"{self.url.rstrip('/')}/data", payload)
            result = {
                "sent": status < 400,
                "disabled": False,
                "status": status,
                "intersection_id": intersection_id,
            }
            logger.info(f"TMC data push {intersection_id} (status {status})")
        except (urllib.error.URLError, urllib.error.HTTPError,
                OSError, ValueError) as e:
            result = {
                "sent": False,
                "disabled": False,
                "status": None,
                "intersection_id": intersection_id,
                "reason": f"TMC unreachable ({e.__class__.__name__})",
            }
            logger.warning(f"TMC data push failed: {str(e)}")

        self.last_push = result
        return result

    def notify(self, alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Deliver an alert payload to every configured webhook URL.

        Parameters
        ----------
        alert : dict
            JSON-serializable alert, e.g.
            {"type": "ANOMALY", "severity": "HIGH", "message": "..."}.

        Returns
        -------
        list[dict]
            One result per webhook:
            {"url", "delivered", "status"|None, "reason"?}
        """
        if not self.webhook_urls:
            self.last_notifications = []
            return []

        payload = dict(alert)
        payload.setdefault("notified_at", datetime.utcnow().isoformat())

        results: List[Dict[str, Any]] = []
        for url in self.webhook_urls:
            try:
                status, _ = self._post_json(url, payload)
                results.append({
                    "url": url,
                    "delivered": status < 400,
                    "status": status,
                })
            except (urllib.error.URLError, urllib.error.HTTPError,
                    OSError, ValueError) as e:
                results.append({
                    "url": url,
                    "delivered": False,
                    "status": None,
                    "reason": f"{e.__class__.__name__}",
                })
                logger.warning(f"TMC webhook {url} failed: {str(e)}")

        delivered = sum(1 for r in results if r["delivered"])
        logger.info(
            f"TMC notifications: {delivered}/{len(results)} delivered "
            f"(type={alert.get('type', 'unknown')})"
        )
        self.last_notifications = results
        return results

    def get_status(self) -> Dict[str, Any]:
        """Client configuration and recent activity."""
        return {
            "configured_url": self.url or "none (disabled)",
            "api_key_set": bool(self.api_key),
            "webhook_urls": self.webhook_urls,
            "webhook_count": len(self.webhook_urls),
            "last_push": self.last_push,
            "last_notifications": self.last_notifications,
            "uptime_s": round(time.time() - self._started_at, 1),
        }

    # ── HELPERS ────────────────────────────────────────────────

    def _post_json(self, url: str, payload: Dict[str, Any]):
        """POST a JSON payload; returns (status, body)."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.status, resp.read()
