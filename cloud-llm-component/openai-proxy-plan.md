# OpenAI-Compatible Proxy — Implementation Plan

## Overview

Build a lightweight Python + FastAPI application in `proxy/` that acts as a transparent
OpenAI-compatible reverse proxy. Every request received on the local endpoint is
authenticated with `LOCAL_API_KEY`, then forwarded verbatim (headers stripped / replaced)
to the upstream cloud endpoint identified by `CLOUD_URL`, authenticating with `CLOUD_API_KEY`.
Streaming (`text/event-stream`) responses are forwarded chunk-by-chunk so callers never
need to know they are talking to a proxy.

The application is packaged as a container image via the existing `proxy/Containerfile`
and deployed by the Podman/TCE infrastructure alongside the `podman/` configuration that
already contains `values.yaml`, `values.schema.json`, and the template.

### Environment variables

| Variable | Purpose |
|---|---|
| `CLOUD_URL` | Base URL of the upstream OpenAI-compatible endpoint (e.g. `https://provider/v1`) |
| `CLOUD_API_KEY` | Bearer token for the upstream endpoint |
| `LOCAL_API_KEY` | Bearer token that callers must present to the proxy |
| `LOG_LEVEL` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Sub-Task 1 — Application source code (`proxy/main.py`)

**Intent**
Create the FastAPI application that catches all paths under `/v1/*`, validates the
incoming `Authorization: Bearer <LOCAL_API_KEY>` header, then proxies the request
(body, query parameters, headers) to `CLOUD_URL` while injecting `CLOUD_API_KEY`.
Streaming and non-streaming paths must both be handled correctly.

**Expected Outcomes**
- `proxy/main.py` exists and is runnable with `uvicorn proxy.main:app`
- A request with a wrong API key receives `HTTP 401` and is never forwarded
- A non-streaming request is fully forwarded and the upstream response is returned intact
- A streaming request (`stream: true` in body or `Accept: text/event-stream`) is forwarded
  and SSE chunks are relayed to the caller as they arrive
- At `LOG_LEVEL=DEBUG`, full sanitised request and response bodies are logged
- At `LOG_LEVEL=INFO` and above, only method, path, status code, and latency are logged

**Todo List**
1. Create `proxy/main.py` with a FastAPI `app` instance
2. Read `CLOUD_URL`, `CLOUD_API_KEY`, `LOCAL_API_KEY`, `LOG_LEVEL` from environment on
   startup; fail fast with a clear error if any required variable is missing
3. Configure Python `logging` using `LOG_LEVEL`; sanitise API key values from log output
4. Implement a dependency `verify_api_key(request)` that checks
   `Authorization: Bearer {LOCAL_API_KEY}`; return `HTTP 401` on mismatch
5. Implement a catch-all route `@app.api_route("/{path:path}", methods=[...])` that
   covers all HTTP verbs used by OpenAI (`GET`, `POST`, `DELETE`)
6. In the route handler, build the upstream URL by joining `CLOUD_URL` and the incoming
   path + query string
7. Forward relevant headers (Content-Type, etc.) while replacing `Authorization` with
   `Bearer {CLOUD_API_KEY}`; strip hop-by-hop headers
8. Detect streaming: check `"stream": true` in JSON body (if content-type is JSON) and/or
   `Accept: text/event-stream`
9. For non-streaming: use `httpx.AsyncClient` to perform the upstream request and return
   a `Response` with the upstream status, headers, and body
10. For streaming: use `httpx.AsyncClient.stream()` and return a `StreamingResponse` that
    yields chunks as they arrive
11. Add DEBUG-level log statements for sanitised request/response bodies; INFO-level log
    for method, path, upstream URL, status, latency

**Relevant Context**
- `podman/values.yaml` maps values to `cloud_url`, `cloud_api_key`, `api_key` — the
  container will receive these as `CLOUD_URL`, `CLOUD_API_KEY`, `LOCAL_API_KEY`
- Use the settings.py file in src/ for accessing these environment variable settings with pydantic settings.

**Status:** `[ ] pending`

---

## Sub-Task 2 — Python dependencies (`proxy/requirements.txt`)

**Intent**
Declare all Python package dependencies needed so they can be installed reproducibly
inside the container and locally.

**Expected Outcomes**
- `proxy/requirements.txt` lists `fastapi`, `uvicorn[standard]`, `httpx` with pinned
  minimum versions that are currently actively maintained

**Todo List**
1. Create `proxy/requirements.txt` with the following packages (latest stable, actively
   maintained as of plan date):
   - `fastapi>=0.115.0`
   - `uvicorn[standard]>=0.32.0`
   - `httpx>=0.28.0`
   - `pydantic-settings` (determine latest version and pin it)

**Relevant Context**
- Security rule: use latest stable, actively maintained versions
- No existing requirements file in `proxy/`

**Status:** `[ ] pending`

---

## Sub-Task 3 — Container image (`proxy/Containerfile`)

**Intent**
Fill in the empty `proxy/Containerfile` with a minimal, secure, non-root container image
built on Red Hat UBI (per IBM security policy) that installs the Python dependencies and
runs the FastAPI app via `uvicorn`.

**Expected Outcomes**
- `proxy/Containerfile` builds successfully with `podman build`
- The container runs as a non-root user
- The app listens on port `8080`
- The image is based on `registry.redhat.io/ubi9/python-311-minimal:latest`
- The container must run on ppc64le architecture
- use the following env directives to install all python packages:
```dockerfile
ENV PIP_PREFER_BINARY=true
ENV PIP_EXTRA_INDEX_URL="https://wheels.developerfirst.ibm.com/ppc64le/linux https://repo.fury.io/mgiessing"
```

**Todo List**
1. Set `FROM registry.redhat.io/ubi9/python-311-minimal:latest`
2. Create a non-root user (`appuser`, UID 1001)
3. Set `WORKDIR /app`
4. Copy `requirements.txt` and run `pip install --no-cache-dir -r requirements.txt`
5. Copy `main.py` into `/app/`
6. Declare `ENV` defaults for `LOG_LEVEL=INFO` and `PORT=8080`
7. `EXPOSE 8080`
8. Switch to `USER 1001`
9. Set `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]`

**Relevant Context**
- `proxy/Containerfile` currently empty
- IBM security rule: base image must come from `registry.redhat.io`; container must run
  non-root; service must not bind to `0.0.0.0`

**Status:** `[ ] pending`

---

## Sub-Task 4 — Podman deployment template (`podman/templates/proxy-api.yaml.tmpl`)

**Intent**
Fill in the empty Podman template that wires the `values.yaml` configuration values into
the container as environment variables and exposes the service port.

**Expected Outcomes**
- `podman/templates/proxy-api.yaml.tmpl` is a valid Podman pod/container spec template
  referencing all four environment variables from `values.yaml`
- The template file name matches the reference in `podman/metadata.yaml`
  (note: `metadata.yaml` currently has a typo `proxy-api.taml.tmpl` — fix to
  `proxy-api.yaml.tmpl` in the same sub-task)

**Todo List**
1. Write a Podman quadlet / container unit template that:
   - Sets `CLOUD_URL` from `{{ .Values.cloud_url }}`
   - Sets `CLOUD_API_KEY` from `{{ .Values.cloud_api_key }}`
   - Sets `LOCAL_API_KEY` from `{{ .Values.api_key }}`
   - Sets `LOG_LEVEL` from `{{ .Values.log_level }}`
   - Exposes the container port `8080` mapped to `{{ .Values.port }}`
2. Fix the typo in `podman/metadata.yaml`: `proxy-api.taml.tmpl` → `proxy-api.yaml.tmpl`

**Relevant Context**
- `podman/values.yaml` — source of all configurable values
- `podman/metadata.yaml` — lists `podTemplateExecutions`; has a typo to fix

**Status:** `[ ] pending`

---

## Sub-Task 5 — Update `includes.txt` and smoke-test documentation

**Intent**
Ensure the `proxy/` directory is included in the archive produced by `make archive` and
add a minimal README so the proxy can be understood and tested locally.

**Expected Outcomes**
- `includes.txt` does not reference any proxy files. The proxy will be build as a container image and pushed to a registry.
- `proxy/README.md` documents the four environment variables, how to build the image
  locally, and a `curl` smoke-test example

**Todo List**
1. Add `./proxy` to `includes.txt`
2. Create `proxy/README.md` with:
   - Description of what the proxy does
   - Table of environment variables
   - Local build command: `podman build -t openai-proxy proxy/`
   - Local run example with all four env vars set
   - `curl` smoke-test against the local container

**Relevant Context**
- `includes.txt` currently lists `./podman` and `./metadata.yaml`
- `Makefile` uses `includes.txt` to build `cloud-llm.tar.gz`

**Status:** `[ ] pending`
