# cloud-llm-proxy

A minimal OpenAI-compatible reverse proxy built with FastAPI.
It authenticates incoming requests with a local API key and forwards them transparently to any OpenAI-compatible upstream endpoint, injecting the upstream API key automatically.
Full SSE streaming is supported.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `CLOUD_URL` | ✅ | Base URL of the upstream endpoint, e.g. `https://provider/v1` |
| `CLOUD_API_KEY` | ✅ | Bearer token for the upstream endpoint |
| `LOCAL_API_KEY` | ☐ | Bearer token callers must present. If empty, auth is disabled. |
| `LOG_LEVEL` | ☐ | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default: `INFO`) |

At `LOG_LEVEL=DEBUG` full request/response bodies are logged (API key values are never logged).

## Build

```bash
podman build -t cloud-llm-proxy:dev .
```

Run from the project root (the Containerfile expects `src/` to be a sibling of `requirements.txt`):

```bash
podman build -t cloud-llm-proxy:dev -f proxy/Containerfile proxy/
```

## Run locally

```bash
podman run --rm \
  -p 8080:8080 \
  -e CLOUD_URL=https://api.openai.com/v1 \
  -e CLOUD_API_KEY=sk-... \
  -e LOCAL_API_KEY=my-local-secret \
  -e LOG_LEVEL=INFO \
  cloud-llm-proxy:dev
```

## Smoke tests

### Health check
```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### List models (forwarded to upstream)
```bash
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer my-local-secret"
```

### Chat completion (non-streaming)
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer my-local-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Chat completion (streaming)
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer my-local-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

### Wrong API key → 401
```bash
curl -i http://localhost:8080/v1/models \
  -H "Authorization: Bearer wrong-key"
# HTTP/1.1 401 Unauthorized
```
