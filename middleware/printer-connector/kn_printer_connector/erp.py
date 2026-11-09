"""Klien HTTP ERP (urllib, tanpa dependensi). Device key dikirim di header `X-Device-Key`, tidak pernah di-log."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import VERSION


class ErpUnavailable(Exception):
    """Jaringan putus / timeout / 5xx — boleh dicoba ulang dengan identitas yang sama."""


class ErpError(Exception):
    def __init__(self, status: int, code: str, message: str, body: Any = None):
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message, self.body = status, code, message, body


def _detail(body: Any) -> Tuple[str, str]:
    d = body.get("detail") if isinstance(body, dict) else body
    if isinstance(d, dict):
        return str(d.get("code") or ""), str(d.get("message") or d)
    return "", str(d)


class ErpClient:
    def __init__(self, base_url: str, device_key: str, instance_id: str, *, verify_tls: bool = True,
                 timeout_s: float = 15.0):
        self.base = base_url.rstrip("/")
        self._key = device_key
        self.instance_id = instance_id
        self.timeout = timeout_s
        self._ctx = None if verify_tls else ssl._create_unverified_context()  # noqa: SLF001 — hanya bila diminta

    def _req(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "X-Device-Key": self._key, "X-Connector-Instance": self.instance_id, "Content-Type": "application/json",
            "User-Agent": f"kn-printer-connector/{VERSION}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                parsed = json.loads(e.read() or b"{}")
            except ValueError:
                parsed = {}
            if e.code >= 500 or e.code == 429:
                raise ErpUnavailable(f"HTTP {e.code}")
            code, msg = _detail(parsed)
            raise ErpError(e.code, code or f"HTTP_{e.code}", msg, parsed)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise ErpUnavailable(str(e))

    def config(self) -> Dict[str, Any]:
        return self._req("GET", "/rfid/printer-agent/config")

    def telemetry(self, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._req("POST", "/rfid/printer-agent/telemetry", {**body, "instance_id": self.instance_id})

    def claim(self, limit: int = 1) -> Dict[str, Any]:
        return self._req("POST", "/rfid/device-jobs/claim", {"limit": limit, "instance_id": self.instance_id})

    def attempt(self, job_id: str, attempt_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/rfid/device-jobs/{job_id}/attempts/{attempt_id}")

    def renew(self, job_id: str, attempt_id: str) -> Dict[str, Any]:
        return self._req("POST", f"/rfid/device-jobs/{job_id}/attempts/{attempt_id}/renew",
                         {"instance_id": self.instance_id})

    def start(self, job_id: str, attempt_id: str, item_ids: List[str], revision: Optional[int]) -> Dict[str, Any]:
        return self._req("POST", f"/rfid/device-jobs/{job_id}/attempts/{attempt_id}/start",
                         {"item_ids": item_ids, "job_revision": revision, "instance_id": self.instance_id})

    def results(self, job_id: str, attempt_id: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._req("POST", f"/rfid/device-jobs/{job_id}/attempts/{attempt_id}/results",
                         {"results": results, "instance_id": self.instance_id})
