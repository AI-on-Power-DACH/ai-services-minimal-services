# OpenAI Compatible Cloud LLM Component

This component acts as an OpenAI-compatible reverse proxy for Spyre [AI Services](https://github.com/IBM/project-ai-services) Bring-Your-Own-Service (BYOS) framework. It brokers LLM requests to an upstream OpenAI-compatible cloud or remote endpoint, injecting authentication and handling streaming transparently.

The service and container image are built for and deployed on **IBM Power 11 (ppc64le architecture)**.


## UI Configuration

NOTE: In the UI the LLM model name (as accepted by the cloud in the requests JSON `model` field) must be given. This value is overriden in the proxy. What model the application requests is irrelevant. This is done as a workaround the current ai-services implementation that requires a valid Huggingface model ID which is passed to a service using the `LLM_MODEL` varaiable.


---

## Directory Structure

```
cloud-llm-component/
├── Makefile                     # Build, container, packaging, and deployment automation
├── includes.txt                 # Manifest of files bundled into the catalog archive
├── metadata.yaml                # AI Services catalog metadata
├── podman/                      # Podman deployment specification
│   ├── metadata.yaml            # Pod execution metadata and resource requirements
│   ├── values.yaml              # Default configuration values
│   ├── values.schema.json       # JSON schema for UI 
│   └── templates/               # Go template files for Pod and Secret specs
│       ├── proxy-api.yaml.tmpl
│       ├── openai-cloud-llm-secret.yaml.tmpl
│       └── openai-cloud-llm-cloud-secret.yaml.tmpl
└── proxy/                       # Application business logic & container source
    ├── Containerfile            # ppc64le OCI image definition (UBI9 Python 3.14)
    ├── requirements.txt         # Python dependencies
    └── src/                     # FastAPI proxy source code (main.py, settings.py)
```

---

## Makefile Variables Reference

All variables use the `?=` operator, allowing them to be configured via the Makefile, command-line arguments, or environment variables.

| Variable | Default Value | Description |
|---|---|---|
| `CONTAINER_REGISTRY` | `quay.io` | OCI image registry host |
| `CONTAINER_REPO` | `<your-username>` | Registry user, namespace, or organization |
| `CONTAINER_IMAGE` | `llm_proxy` | Container image repository name |
| `CONTAINER_TAG` | `dev` | Container image tag |
| `SSH_TARGET` | `power-host` | SSH host/alias for the IBM Power 11 target machine |
| `REMOTE_WORKDIR` | `~/cloud-llm` | Working directory on the remote SSH target |
| `CATALOG_ID` | `llm--openai-cloud-llm` | Catalog bundle identifier in AI Services |
| `CATALOG_SERVER` | `https://catalog-ui.<domain>.nip.io` | AI Services catalog server URL |
| `CATALOG_USER` | `admin` | AI Services catalog login user |
| `CATALOG_PASSWORD_FILE` | `~/aipw.txt` | Path to password file on remote host for catalog login |
| `ARCHIVE_NAME` | `cloud-llm.tar.gz` | Output name of the catalog release bundle |
| `INCLUDE_FILE` | `includes.txt` | File list manifest for the catalog bundle |

---

## Setting Variables

You can configure these variables in three ways:

### 1. Via Command Line (Recommended)

Pass variables directly when invoking `make`:

```bash
# Build container image with a custom registry repo and tag
make CONTAINER_REPO=myorg CONTAINER_TAG=v1.1.2 build-image

# Push container image
make CONTAINER_REPO=myorg CONTAINER_TAG=v1.1.2 push-image

# Transfer and build remotely on IBM Power 11 target
make SSH_TARGET=power11-node REMOTE_WORKDIR=/home/user/build CONTAINER_REPO=myorg containerupdate

# Update the catalog bundle on the remote host
make SSH_TARGET=power11-node CATALOG_SERVER=https://catalog.example.com tceupdate
```

### 2. By Editing the Makefile

Edit the default values directly at the top of [`Makefile`](cloud-llm-component/Makefile):

```makefile
SSH_TARGET ?= my-power-server
REMOTE_WORKDIR ?= /home/user/cloud-llm
CONTAINER_REGISTRY ?= quay.io
CONTAINER_REPO ?= my-username
CONTAINER_IMAGE ?= llm_proxy
CONTAINER_TAG ?= 1.1.2
```

### 3. Via Environment Variables

Export the variables in your shell before running `make`:

```bash
export CONTAINER_REPO=myorg
export CONTAINER_TAG=1.1.2
export SSH_TARGET=power11-node

make build-image
make containertransfer
```

---

## Step-by-Step Build & Deployment Guide

### Step 1: Build the OCI Container Image (ppc64le)

The container image is built from [`proxy/Containerfile`](cloud-llm-component/proxy/Containerfile) on Red Hat UBI 9 using ppc64le binary wheels from the IBM Power repository.

* **Option A — Build locally (if running directly on an IBM Power machine):**
  ```bash
  make CONTAINER_REPO=<your-username> CONTAINER_TAG=<tag> build-image
  make CONTAINER_REPO=<your-username> CONTAINER_TAG=<tag> push-image
  ```

* **Option B — Build remotely (from development machine to Power 11 host over SSH):**
  ```bash
  make SSH_TARGET=<power-host> \
       CONTAINER_REPO=<your-username> \
       CONTAINER_TAG=<tag> \
       containerupdate
  ```
  *This cleans `__pycache__`, transfers `proxy/` to `SSH_TARGET:REMOTE_WORKDIR`, runs `podman build`, and executes `podman push` on the remote host.*

### Step 2: Build the AI Services Catalog Bundle

Create the `.tar.gz` bundle containing the `podman/` definitions and `metadata.yaml` required by AI Services:

```bash
make archive
```

To inspect the files included in the generated archive:

```bash
make inspect
```

### Step 3: (Optional) Validate Pod Spec Locally

You can render and test the Go templates locally using the root `render_template.py` script:

```bash
# Render specification to stdout
python3 ../render_template.py -m podman/metadata.yaml -f podman/values.yaml

# Render and run with Podman
python3 ../render_template.py -m podman/metadata.yaml -f podman/values.yaml --run
```

### Step 4: Deploy / Update Catalog Bundle in AI Services

* **Via Makefile (SSH automation):**
  ```bash
  make SSH_TARGET=<power-host> \
       CATALOG_SERVER=https://catalog-ui.<cluster-ip>.nip.io \
       CATALOG_PASSWORD_FILE=~/aipw.txt \
       tceupdate
  ```

* **Via AI Services Catalog UI:**
  1. Open the AI Services web UI.
  2. Navigate to Catalog / Bundles.
  3. Upload `cloud-llm.tar.gz`.

---

## Clean Up

Remove the generated archive:

```bash
make clean
```
