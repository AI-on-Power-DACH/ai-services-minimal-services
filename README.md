# Spyre AI Services - Minimal Services (BYOS)

This repository contains custom services and components demonstrating the **Bring Your Own Service (BYOS)** capabilities for IBM Spyre [AI Services](https://github.com/IBM/project-ai-services).

Both services are specifically targeted, built, and tested for **IBM Power 11 hardware (`ppc64le` architecture)** in a standalone (LPAR) deployment (podman services).

---

## Projects Overview

| Directory | Type | Description |
|---|---|---|
| [`cloud-llm-component/`](cloud-llm-component/README.md) | Component (`llm`) | FastAPI reverse proxy that forwards OpenAI-compatible LLM requests to an upstream cloud endpoint. |
| [`emotion-service/`](emotion-service/README.md) | Service (`standalone`) | Emotion classification API that analyzes messages and classifies sentiment using an LLM backend service. |

---

## Repository Structure

Each project directory contains two main components:
1. **`podman/` Directory:** Defines the service specifications for AI Services:
   - `metadata.yaml`: Service resource requirements (CPU, memory, storage) and template execution list.
   - `values.yaml`: Default configuration values.
   - `values.schema.json`: JSON schema driving the configuration UI in the AI Services catalog.
   - `templates/*.yaml.tmpl`: Go templates rendered by AI Services into runnable Kubernetes/Podman pod specifications.
2. **Source Code & `Containerfile` (`proxy/` or `emotion/`):** Contains the Python application logic and Containerfile used to build the OCI container image for `ppc64le`.

In addition:
- `includes.txt`: Lists files included in the `.tar.gz` bundle for the AI Services catalog.
- `render_template.py`: A local utility to render Go templates with `values.yaml` and test them with `podman play kube`.

For more information on how the services work and how to write one, see [the official documentation](https://github.com/IBM/project-ai-services/tree/main/docs/dev-guides/byos).

---

## Quick Start

### 1. Build and Package Cloud LLM Component

```bash
cd cloud-llm-component

# Build OCI image (ppc64le)
make CONTAINER_REPO=<your-username> CONTAINER_TAG=1.1.2 build-image

# Package the AI Services catalog bundle
make archive
```

For detailed instructions and remote deployment on IBM Power 11, see [`cloud-llm-component/README.md`](cloud-llm-component/README.md).

### 2. Build and Package Emotion Service

```bash
cd emotion-service

# Build OCI image (ppc64le)
make CONTAINER_REPO=<your-username> CONTAINER_TAG=1.1.0 build-image

# Package the AI Services catalog bundle
make archive
```

For detailed instructions and remote deployment on IBM Power 11, see [`emotion-service/README.md`](emotion-service/README.md).

---

## Common Makefile Variables

Both services use parameterized Makefiles with the `?=` operator:

| Variable | Description | Example Override |
|---|---|---|
| `CONTAINER_REGISTRY` | Container registry | `make CONTAINER_REGISTRY=quay.io ...` |
| `CONTAINER_REPO` | Registry namespace/user | `make CONTAINER_REPO=myorg ...` |
| `CONTAINER_TAG` | Image tag | `make CONTAINER_TAG=v1.0.0 ...` |
| `SSH_TARGET` | IBM Power 11 host SSH alias | `make SSH_TARGET=power11-host ...` |
| `REMOTE_WORKDIR` | Remote build directory | `make REMOTE_WORKDIR=/home/user/build ...` |
| `CATALOG_SERVER` | AI Services catalog server | `make CATALOG_SERVER=https://catalog.example.com ...` |
