import json
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx2 as httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from settings import LLMProxySettings

# ---------------------------------------------------------------------------
# Startup / settings
# ---------------------------------------------------------------------------

settings: LLMProxySettings  # populated in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global settings
    settings = LLMProxySettings()  # raises ValidationError if required vars missing
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    yield


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("llm-proxy")

# ---------------------------------------------------------------------------
# Headers to strip before forwarding (hop-by-hop + proxy internals)
# ---------------------------------------------------------------------------

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",  # httpx recalculates this
    }
)


def _build_upstream_headers(request: Request) -> dict[str, str]:
    """Forward safe headers, replacing Authorization with the cloud API key."""
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    headers["authorization"] = (
        f"Bearer {settings.cloud_api_key.get_secret_value()}"
    )
    return headers


def _build_upstream_url(request: Request) -> str:
    """Combine CLOUD_URL (without trailing slash) with the incoming path + query."""
    base = str(settings.cloud_url).rstrip("/")
    path = request.url.path
    qs = request.url.query
    url = f"{base}{path}"
    if qs:
        url = f"{url}?{qs}"
    return url


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def verify_api_key(request: Request) -> None:
    """Return 401 if LOCAL_API_KEY is configured and the caller does not match."""
    local_key = settings.api_key
    if local_key is None or local_key.get_secret_value() == "":
        # No key configured — open access (useful for development)
        return
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or token != local_key.get_secret_value():
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Health endpoint (used by the liveness probe)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Catch-all proxy route
# ---------------------------------------------------------------------------


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    dependencies=[Depends(verify_api_key)],
)
async def proxy(request: Request, path: str) -> Response:  # noqa: ARG001
    upstream_url = _build_upstream_url(request)
    headers = _build_upstream_headers(request)
    body = await request.body()

    # Detect streaming intent & rewrite model if cloud_model_id is configured
    is_streaming = False
    if "application/json" in request.headers.get("content-type", ""):
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                is_streaming = bool(payload.get("stream", False))
                if settings.cloud_model_id and "model" in payload:
                    payload["model"] = settings.cloud_model_id
                    body = json.dumps(payload).encode("utf-8")
        except (json.JSONDecodeError, AttributeError):
            pass
    if request.headers.get("accept", "") == "text/event-stream":
        is_streaming = True

    logger.info(
        "→ %s %s upstream=%s streaming=%s",
        request.method,
        request.url.path,
        upstream_url,
        is_streaming,
    )
    if logger.isEnabledFor(logging.DEBUG) and body:
        logger.debug("request body: %s", body.decode(errors="replace"))

    start = time.monotonic()

    if is_streaming:
        return await _stream_response(request.method, upstream_url, headers, body, start)
    return await _full_response(request.method, upstream_url, headers, body, start)


async def _full_response(
    method: str, url: str, headers: dict, body: bytes, start: float
) -> Response:
    async with httpx.AsyncClient(timeout=300) as client:
        upstream = await client.request(method, url, headers=headers, content=body)

    elapsed = time.monotonic() - start
    logger.info("← %s %s %.3fs", upstream.status_code, url, elapsed)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("response body: %s", upstream.text)

    # Strip hop-by-hop from upstream response headers
    resp_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )


async def _stream_response(
    method: str, url: str, headers: dict, body: bytes, start: float
) -> StreamingResponse:
    async def _iter():
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(method, url, headers=headers, content=body) as r:
                logger.info(
                    "← streaming %s %s %.3fs first-byte",
                    r.status_code,
                    url,
                    time.monotonic() - start,
                )
                async for chunk in r.aiter_bytes():
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("stream chunk: %s", chunk.decode(errors="replace"))
                    yield chunk

    return StreamingResponse(_iter(), media_type="text/event-stream")
