# Message Emotion Classification Service

This is an [AI Services](https://github.com/IBM/project-ai-services) compatible service that classifies a message by how the author likely felt while writing it. It connects to an LLM dependency (such as the Cloud LLM component or vLLM service) to perform emotion classification on messages.

The purpose of this service is to demonstrate and test the AI Services Bring-Your-Own-Service (BYOS) capabilities. It is built for and deployed on **IBM Power 11 (ppc64le architecture)**.

---

## Directory Structure

```
emotion-service/
├── Makefile                     # Build, container, packaging, and deployment automation
├── includes.txt                 # Manifest of files bundled into the catalog archive
├── metadata.yaml                # AI Services catalog metadata
├── podman/                      # Podman deployment specification
│   ├── metadata.yaml            # Pod execution metadata and resource requirements
│   ├── values.yaml              # Default configuration values
│   ├── values.schema.json       # JSON schema for UI and configuration validation
│   └── templates/               # Go template files for Pod specs
│       └── emotion-api.yaml.tmpl
└── emotion/                     # Application business logic & container source
    ├── Containerfile            # ppc64le OCI image definition (UBI9 Python 3.12)
    └── src/                     # Emotion classification FastAPI application
        ├── app.py               # Main application entry point
        ├── classification.py    # Classification logic
        ├── llmcall.py           # LLM client communication
        ├── emotion_types.py     # Data models and schemas
        ├── settings.py          # Environment settings
        └── requirements.txt     # Python dependencies
```

---

## Makefile Variables Reference

All variables use the `?=` operator, allowing them to be configured via the Makefile, command-line arguments, or environment variables.

| Variable | Default Value | Description |
|---|---|---|
| `CONTAINER_REGISTRY` | `quay.io` | OCI image registry host |
| `CONTAINER_REPO` | `<your-username>` | Registry user, namespace, or organization |
| `CONTAINER_IMAGE` | `emotion-service` | Container image repository name |
| `CONTAINER_TAG` | `dev` | Container image tag |
| `SSH_TARGET` | `power-host` | SSH host/alias for the IBM Power 11 target machine |
| `REMOTE_WORKDIR` | `~/emotion` | Working directory on the remote SSH target |
| `CATALOG_ID` | `emotion` | Catalog bundle identifier in AI Services |
| `CATALOG_SERVER` | `https://catalog-ui.<domain>.nip.io` | AI Services catalog server URL |
| `CATALOG_USER` | `admin` | AI Services catalog login user |
| `CATALOG_PASSWORD_FILE` | `~/aipw.txt` | Path to password file on remote host for catalog login |
| `ARCHIVE_NAME` | `emotion-service.tar.gz` | Output name of the catalog release bundle |
| `INCLUDE_FILE` | `includes.txt` | File list manifest for the catalog bundle |

---

## Setting Variables

You can configure these variables in three ways:

### 1. Via Command Line (Recommended)

Pass variables directly when invoking `make`:

```bash
# Build container image with custom repository and tag
make CONTAINER_REPO=myorg CONTAINER_TAG=v1.1.0 build-image

# Push container image to registry
make CONTAINER_REPO=myorg CONTAINER_TAG=v1.1.0 push-image

# Transfer source, build on remote IBM Power 11 host, and push
make SSH_TARGET=power11-node REMOTE_WORKDIR=/home/user/emotion CONTAINER_REPO=myorg containerupdate

# Update the catalog bundle on the remote host
make SSH_TARGET=power11-node CATALOG_SERVER=https://catalog.example.com tceupdate
```

### 2. By Editing the Makefile

Edit default values directly at the top of [`Makefile`](emotion-service/Makefile):

```makefile
SSH_TARGET ?= my-power-server
REMOTE_WORKDIR ?= /home/user/emotion
CONTAINER_REGISTRY ?= quay.io
CONTAINER_REPO ?= my-username
CONTAINER_IMAGE ?= emotion-service
CONTAINER_TAG ?= 1.1.0
```

### 3. Via Environment Variables

Export the variables in your shell before running `make`:

```bash
export CONTAINER_REPO=myorg
export CONTAINER_TAG=1.1.0
export SSH_TARGET=power11-node

make build-image
make containertransfer
```

---

## Step-by-Step Build & Deployment Guide

### Step 1: Build the OCI Container Image (ppc64le)

The container image is built from [`emotion/Containerfile`](emotion-service/emotion/Containerfile) based on Red Hat UBI 9 with ppc64le wheels index from the IBM Power repository.

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
  *This cleans `__pycache__`, transfers `emotion/` to `SSH_TARGET:REMOTE_WORKDIR`, runs `podman build`, and executes `podman push` on the remote host.*

### Step 2: Build the AI Services Catalog Bundle

Create the `.tar.gz` release bundle containing the `podman/` definitions and `metadata.yaml` required by the AI Services catalog:

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
  3. Upload `emotion-service.tar.gz`.

---

## Clean Up

Remove the generated archive:

```bash
make clean
```
