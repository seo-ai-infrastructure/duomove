"""Internal, authenticated, single-process diagnostic service.

This is not a multi-tenant motion executor or distributed device-lease service.
"""
from __future__ import annotations

import math
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .probe import AdbRunner, run_probe, validate_serial


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    targets: Mapping[str, str] = field(repr=False)
    connect: bool = False
    port: int = 8000
    adb_binary: str = 'adb'
    timeout: float = 8

    def __post_init__(self):
        if not isinstance(self.token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', self.token):
            raise ValueError('DUOMOVE_SERVICE_TOKEN must contain 32-256 URL-safe characters')
        if not isinstance(self.targets, dict) or len(self.targets) > 100:
            raise ValueError('ADB targets must be an object with at most 100 aliases')
        for alias, serial in self.targets.items():
            if not isinstance(alias, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', alias):
                raise ValueError('invalid device alias in server configuration')
            validate_serial(serial)
        if type(self.connect) is not bool:
            raise ValueError('connect must be boolean')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('PORT must be between 1 and 65535')
        if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 30:
            raise ValueError('ADB timeout must be between 1 and 30 seconds')
        object.__setattr__(self, 'targets', MappingProxyType(dict(self.targets)))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        import json
        env = os.environ if env is None else env
        try:
            targets = json.loads(env.get('DUOMOVE_ADB_TARGETS_JSON', '{}'))
            port = int(env.get('PORT', '8000'))
            timeout = float(env.get('DUOMOVE_ADB_TIMEOUT_SECONDS', '8'))
        except (ValueError, TypeError):
            raise ValueError('invalid DuoMove server configuration') from None
        connect = env.get('DUOMOVE_ADB_CONNECT', 'false').lower()
        if connect not in ('true', 'false'):
            raise ValueError('DUOMOVE_ADB_CONNECT must be true or false')
        return cls(
            token=env.get('DUOMOVE_SERVICE_TOKEN', ''), targets=targets,
            port=port, timeout=timeout, connect=connect == 'true',
            adb_binary=env.get('DUOMOVE_ADB_BINARY', 'adb'),
        )


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    device_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')


def create_app(settings: Settings | None = None, *, probe: Callable | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title='DuoMove', version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    bearer = HTTPBearer(auto_error=False)
    active = threading.BoundedSemaphore(1)
    last_started: dict[str, float] = {}

    def authorized(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode('utf-8'), settings.token.encode('utf-8')
        ):
            raise HTTPException(401, detail='authentication_required', headers={'WWW-Authenticate': 'Bearer'})

    @app.middleware('http')
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Do not reflect submitted credentials, addresses or body fields.
        return JSONResponse(status_code=422, content={'detail': 'invalid_probe_request'})

    @app.get('/healthz')
    def health():
        return {'status': 'ok', 'scope': 'http_service_only', 'motion_enabled': False}

    @app.get('/v1/status', dependencies=[Depends(authorized)])
    def status():
        return {
            'service': 'duomove', 'version': __version__, 'mode': 'diagnostics_only',
            'configured_devices': sorted(settings.targets), 'motion_enabled': False,
            'blocked_reason': 'original_motion_package_not_integrated',
            'location_writers': {
                'DUOPLUS_REST': 'not_integrated', 'ADB_SHELL': 'disabled', 'ADB_HELPER': 'disabled',
            },
        }

    @app.post('/v1/probes', dependencies=[Depends(authorized)])
    def probe_device(body: ProbeRequest):
        serial = settings.targets.get(body.device_id)
        if serial is None:
            raise HTTPException(404, detail='device_not_configured')
        if not active.acquire(blocking=False):
            raise HTTPException(409, detail='probe_already_running')
        try:
            now = time.monotonic()
            previous = last_started.get(body.device_id)
            if previous is not None and now - previous < 30:
                retry = max(1, math.ceil(30 - (now - previous)))
                raise HTTPException(429, detail='probe_cooldown', headers={'Retry-After': str(retry)})
            last_started[body.device_id] = now
            try:
                if probe is not None:
                    return probe(serial, device_id=body.device_id, connect=settings.connect)
                runner = AdbRunner(serial, binary=settings.adb_binary, timeout=settings.timeout)
                return run_probe(serial, device_id=body.device_id, connect=settings.connect, runner=runner)
            except Exception:
                raise HTTPException(502, detail='probe_execution_failed') from None
        finally:
            active.release()

    @app.post('/v1/motion', dependencies=[Depends(authorized)])
    def motion_disabled():
        raise HTTPException(409, detail='motion_executor_not_integrated')

    return app
