"""Inquiry router API, one deployment per authority.

- Tokens come from the authority's own Keycloak realm. A token from another realm, without the role, or
  for another audience is refused before any model code runs.
- Model artifacts are loaded only after their sha256 matches the digests pinned in git
  (tenants/<name>.yaml -> Helm values -> env). Until then /readyz says no, so Kubernetes sends no traffic.
- Logs are JSON, one line per request, with the trace id, the adapter digest and a hash of the inquiry;
  never the inquiry itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
from fastapi import FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from sov.config import platform
from sov.ml.registry import IntegrityError, Registry
from sov.serve.infer import DEPARTMENTS, NumpyRouter

log = logging.getLogger("sov.api")


def _emit(event: str, **fields: Any) -> None:
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
    print(json.dumps(line, ensure_ascii=False), file=sys.stdout, flush=True)


@dataclass
class Settings:
    tenant: str
    base: str
    adapter: str | None
    registry: Path
    issuer: str
    audience: str
    jwks_url: str

    @classmethod
    def from_env(cls) -> Settings:
        issuer = os.environ["SOV_ISSUER"]
        adapter = os.environ.get("SOV_ADAPTER_DIGEST") or None
        return cls(
            tenant=os.environ["SOV_TENANT"],
            base=os.environ["SOV_BASE_DIGEST"],
            adapter=adapter,
            registry=Path(os.environ.get("SOV_REGISTRY", "/models")),
            issuer=issuer,
            audience=os.environ.get("SOV_AUDIENCE", "inquiry-router-api"),
            jwks_url=os.environ.get("SOV_JWKS_URL", issuer.rstrip("/") + "/protocol/openid-connect/certs"),
        )


KeyResolver = Callable[[str], Any]


def jwks_resolver(url: str) -> KeyResolver:
    client = jwt.PyJWKClient(url, cache_keys=True, lifespan=platform()["serve"]["jwks_cache_seconds"])
    return lambda token: client.get_signing_key_from_jwt(token).key


class AuthError(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def check_token(token: str, settings: Settings, resolve: KeyResolver) -> dict[str, Any]:
    cfg = platform()["serve"]
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise AuthError(401, "malformed") from exc
    if unverified.get("iss") != settings.issuer:
        raise AuthError(401, "issuer")  # a token from another authority's realm
    try:
        claims = jwt.decode(
            token,
            resolve(token),
            algorithms=["RS256"],
            audience=settings.audience,
            issuer=settings.issuer,
            leeway=cfg["leeway_seconds"],
        )
    except jwt.InvalidAudienceError as exc:
        raise AuthError(401, "audience") from exc
    except jwt.ExpiredSignatureError as exc:
        raise AuthError(401, "expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError(401, "signature") from exc
    roles = set(claims.get("realm_access", {}).get("roles", []))
    if cfg["required_role"] not in roles:
        raise AuthError(403, "role")
    return claims


class RouteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RouteOut(BaseModel):
    department: str
    confidence: float
    handoff: bool
    trace_id: str
    adapter: str | None
    base: str


def create_app(settings: Settings | None = None, resolve: KeyResolver | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    resolve = resolve or jwks_resolver(settings.jwks_url)
    reg = CollectorRegistry()
    requests = Counter("sov_requests_total", "Routed inquiries", ["tenant", "department", "handoff"], registry=reg)
    latency = Histogram(
        "sov_route_seconds",
        "Time to route one inquiry",
        ["tenant"],
        registry=reg,
        buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
    )
    auth_fail = Counter("sov_auth_failures_total", "Refused requests", ["tenant", "reason"], registry=reg)
    info = Gauge("sov_model_info", "Model artifacts being served", ["tenant", "base", "adapter"], registry=reg)
    integrity = Counter(
        "sov_artifact_integrity_failures_total", "Artifacts that failed the digest check", ["tenant"], registry=reg
    )

    state: dict[str, Any] = {"predictor": None, "error": None}

    def load() -> None:
        try:
            registry = Registry(settings.registry)
            base = registry.get(settings.base)
            adapter = registry.get(settings.adapter) if settings.adapter else None
            state["predictor"] = NumpyRouter(base, adapter)
            info.labels(settings.tenant, settings.base, settings.adapter or "none").set(1)
            _emit("model_loaded", tenant=settings.tenant, base=settings.base, adapter=settings.adapter)
        except IntegrityError as exc:
            integrity.labels(settings.tenant).inc()
            state["error"] = str(exc)
            _emit("artifact_integrity_failed", level="error", tenant=settings.tenant, detail=str(exc))

    load()
    app = FastAPI(title=f"inquiry router ({settings.tenant})", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/readyz")
    def readyz(response: Response) -> dict[str, Any]:
        if state["predictor"] is None:
            response.status_code = 503
            return {"ready": False, "reason": state["error"]}
        return {"ready": True, "tenant": settings.tenant, "adapter": settings.adapter, "base": settings.base}

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(reg), media_type=CONTENT_TYPE_LATEST)

    @app.post("/v1/tenants/{tenant}/route", response_model=RouteOut)
    def route(
        tenant: str,
        body: RouteIn,
        request: Request,
        authorization: str = Header(default=""),
        traceparent: str = Header(default=""),
    ) -> RouteOut:
        trace_id = traceparent.split("-")[1] if traceparent.count("-") >= 3 else uuid.uuid4().hex
        if tenant != settings.tenant:
            raise HTTPException(404, "unknown authority")
        if not authorization.lower().startswith("bearer "):
            auth_fail.labels(settings.tenant, "missing").inc()
            raise HTTPException(401, "bearer token required")
        try:
            claims = check_token(authorization[7:], settings, resolve)
        except AuthError as exc:
            auth_fail.labels(settings.tenant, exc.reason).inc()
            _emit("auth_refused", level="warn", tenant=settings.tenant, trace_id=trace_id, reason=exc.reason)
            raise HTTPException(exc.status, exc.reason) from exc
        predictor: NumpyRouter | None = state["predictor"]
        if predictor is None:
            raise HTTPException(503, "model not loaded")
        start = time.perf_counter()
        proba = predictor.proba([body.text])[0]
        took = time.perf_counter() - start
        best = int(proba.argmax())
        conf = float(proba[best])
        handoff = conf < platform()["serve"]["low_confidence"]
        dept = DEPARTMENTS[best]
        latency.labels(settings.tenant).observe(took)
        requests.labels(settings.tenant, dept, str(handoff).lower()).inc()
        _emit(
            "routed",
            tenant=settings.tenant,
            trace_id=trace_id,
            department=dept,
            confidence=round(conf, 3),
            handoff=handoff,
            adapter=settings.adapter,
            latency_ms=round(took * 1000, 2),
            subject=claims.get("sub"),
            text_sha256=hashlib.sha256(body.text.encode()).hexdigest()[:16],
            text_chars=len(body.text),
        )
        return RouteOut(
            department=dept,
            confidence=round(conf, 4),
            handoff=handoff,
            trace_id=trace_id,
            adapter=settings.adapter,
            base=settings.base,
        )

    return app


def main() -> None:  # pragma: no cover - container entry point
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), access_log=False)


if __name__ == "__main__":  # pragma: no cover
    main()
