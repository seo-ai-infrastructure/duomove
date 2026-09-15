"""Internal probe API. It is not a motion executor or a tenant-authentication layer."""
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from . import __version__
from .probe import AdbReader, probe


@dataclass(frozen=True)
class Settings:
    token: str | None = field(default=None, repr=False)
    targets: Mapping[str, str] = field(default_factory=dict, repr=False)
    adb_executable: str = "adb"
    timeout: float = 10

    def __post_init__(self):
        if self.token is not None and (
            not isinstance(self.token, str) or not 32 <= len(self.token) <= 512
            or not self.token.isascii() or any(c.isspace() for c in self.token)
        ):
            raise ValueError("Internal token must contain 32-512 non-whitespace ASCII characters")
        if not isinstance(self.targets, Mapping) or len(self.targets) > 1000:
            raise ValueError("Targets must be a JSON object with at most 1000 entries")
        for alias, serial in self.targets.items():
            if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", alias):
                raise ValueError("Invalid device alias")
            AdbReader(serial, executable=self.adb_executable, timeout=self.timeout)
        if not 0.1 <= self.timeout <= 30:
            raise ValueError("Invalid probe timeout")
        object.__setattr__(self, "targets", MappingProxyType(dict(self.targets)))

    @classmethod
    def from_environment(cls) -> Settings:
        try:
            targets = json.loads(os.getenv("DUOMOVE_TARGETS_JSON", "{}"))
            timeout = float(os.getenv("DUOMOVE_ADB_TIMEOUT_SECONDS", "10"))
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid DuoMove configuration") from exc
        return cls(token=os.getenv("DUOMOVE_INTERNAL_TOKEN") or None,
                   targets=targets, timeout=timeout,
                   adb_executable=os.getenv("DUOMOVE_ADB_EXECUTABLE", "adb"))


def create_app(settings: Settings | None = None, probe_fn=None) -> FastAPI:
    config = settings if settings is not None else Settings.from_environment()
    execute_probe = probe if probe_fn is None else probe_fn
    # This lock bounds diagnostic resource use only. It is NOT a fleet/location lease.
    probe_lock = threading.Lock()
    app = FastAPI(title="DuoMove Probe", version=__version__, docs_url=None,
                  redoc_url=None, openapi_url=None)

    def authorize(authorization: str | None):
        if config.token is None:
            raise HTTPException(503, "Probe API is not configured")
        scheme, _, supplied = (authorization or "").partition(" ")
        if (scheme.lower() != "bearer" or not supplied.isascii()
                or not hmac.compare_digest(supplied, config.token)):
            raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/healthz")
    def health():
        return {"status": "ok", "service": "duomove", "version": __version__, "mode": "probe_only"}

    @app.get("/v1/status")
    def status(authorization: str | None = Header(default=None)):
        authorize(authorization)
        adb_available = shutil.which(config.adb_executable) is not None
        return {"mode": "probe_only", "adb_available": adb_available,
                "configured_target_count": len(config.targets),
                "probe_configured": adb_available and bool(config.targets),
                "device_connectivity_verified": False,
                "original_motion_source_integrated": False, "motion_execution_enabled": False}

    def run_probe(device_id: str):
        if not probe_lock.acquire(blocking=False):
            raise HTTPException(409, "A probe is already running")
        try:
            report = execute_probe(
                AdbReader(config.targets[device_id], config.adb_executable, config.timeout), device_id
            )
            return JSONResponse(report, status_code=200 if report.get("status") == "complete" else 502)
        except Exception as exc:
            # Never serialize exception messages: they may include private endpoints.
            raise HTTPException(500, "Probe execution failed") from exc
        finally:
            probe_lock.release()

    @app.post("/v1/probes/{device_id}")
    async def start_probe(device_id: str, request: Request,
                          authorization: str | None = Header(default=None)):
        authorize(authorization)
        if device_id not in config.targets:
            raise HTTPException(404, "Unknown device alias")
        # Reject even chunked bodies without buffering them. All input is server-configured.
        async for chunk in request.stream():
            if chunk:
                raise HTTPException(400, "This endpoint accepts no request body")
        return await run_in_threadpool(run_probe, device_id)

    return app
