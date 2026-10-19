# Use an API key in a custom LLM component (Podman)

## Purpose

This document tells you how to add an optional API key to a custom LLM component (`component_type: llm`) for the Podman runtime. It also tells you how a service reads the key.

All names in this document are examples. Use your own component and service names. The only fixed names are the ones the engine sets: `.Values.<component_type>.*`, `.InstanceSlug`, `.Values.<component_type>.instanceSlug`, `.Values.<component_type>.host` and `.Values.<component_type>.port`.

Example names used here:

| Placeholder | Example value | Meaning |
|---|---|---|
| `<component>` | `my-llm` | Prefix for your component's resources |
| `<service>` | `my-service` | Prefix for your service's resources |
| `<KEY_ENV>` | `MY_LLM_API_KEY` | Env variable your LLM server reads |

Reference implementation (uses `vllm-` names): `ai-services/assets/components/llm/vllm-spyre/podman/`.

## How the key gets to the service

There are two separate mechanisms. You must support both.

1. **Values injection (the on/off flag).**
   - The engine reads your component `values.yaml` and applies the user parameters.
   - The engine copies **every top-level field** to the service under the component type: `.Values.<component_type>.<field>`.
   - For `component_type: llm`, the field `apiKey` becomes `.Values.llm.apiKey` in the service templates.
   - The engine also adds `.Values.llm.instanceSlug`, `.Values.llm.host` and `.Values.llm.port`.
   - Code: `ParamBuilder.loadServiceValues()` in `ai-services/internal/pkg/catalog/apiserver/services/params/param_builder.go` and `mergeEndpointIntoService()` in `ai-services/internal/pkg/catalog/apiserver/services/deployment/repository/podman/deployer.go`.
   - The service uses `.Values.llm.apiKey` only in `{{ if }}` checks. It does not write the value into the pod spec.

2. **Secret (the key value).**
   - The component creates a secret that contains the key.
   - The service mounts this secret. It builds the secret name from `.Values.llm.instanceSlug`.
   - The component and the service must use the **same secret name pattern and data key**. Nothing checks this. If they do not match, the service fails at runtime.

You do not set the `llm` prefix yourself. It comes from `component_type: llm` in the top-level `metadata.yaml`. The provider ID (your component `id`) never appears in service values.

## Contract between component and service

You choose the names. Keep them identical on both sides.

| Item | Component side | Service side |
|---|---|---|
| Values field | `apiKey: ""` | `.Values.llm.apiKey` |
| Secret name | `<component>-secret-{{ .InstanceSlug }}` | `<component>-secret-{{ .Values.llm.instanceSlug }}` |
| Secret data key | `apiKey` | file `<mountPath>/apiKey` |
| LLM endpoint | pod name + first `containerPort` | `http://{{ .Values.llm.host }}:{{ .Values.llm.port }}` |

`.InstanceSlug` in the component and `.Values.llm.instanceSlug` in the service have the same value. Always put the slug in the secret name, so that two instances do not share one secret.

**Built-in services use fixed names.** The built-in services (summarize, translate, extract, digitize) expect the field `apiKey`, the secret `vllm-secret-{{ .Values.llm.instanceSlug }}` and the data key `apiKey`. If your component must work with these services, use these exact names. If you write your own service, use any names. The built-in chat service on Podman does not read the key.

## Bundle layout

```
my-llm/
├── metadata.yaml
└── podman/
    ├── metadata.yaml
    ├── values.yaml
    ├── values.schema.json
    └── templates/
        ├── my-llm-secret.yaml.tmpl
        └── my-llm-server.yaml.tmpl
```

The bundle validator rejects the `podman/` folder without `values.schema.json`, even though the docs call it optional.

## Procedure: component

### Step 1: Set the component type

In the top-level `metadata.yaml`, set `component_type: llm`.

```yaml
type: component
id: my-llm
version: "1.0.0"
name: "My LLM provider"
description: "Serves an LLM with an optional API key"
component_type: llm
component_name: "Large language model (LLM)"
```

### Step 2: Add values

In `podman/values.yaml`, add `apiKey` with an empty default. If the key is empty, all key logic is skipped.

Add the other fields that your service needs. All top-level fields are available to the service as `.Values.llm.<field>`. The built-in services also read `model`, `maxModelLen` and `maxBatchSize`.

```yaml
image: "<registry>/<image>:<tag>"
model: ""
apiKey: ""
maxModelLen: 32768
maxBatchSize: 32
```

### Step 3: Expose the key in the UI

Add `apiKey` to `podman/values.schema.json`. Use `"format": "password"` so that the UI masks the value. If you set `"additionalProperties": false`, list every field that users can set.

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "model": { "type": "string", "title": "Model" },
    "apiKey": {
      "type": "string",
      "title": "API key (optional)",
      "format": "password",
      "description": "Optional API key for the LLM endpoint. Leave empty to disable authentication."
    }
  }
}
```

### Step 4: Create the secret template

File: `podman/templates/my-llm-secret.yaml.tmpl`. Create the secret only when a key is set.

```yaml
{{- if .Values.apiKey }}
apiVersion: v1
kind: Secret
metadata:
  name: "my-llm-secret-{{ .InstanceSlug }}"
  labels:
    ai-services.io/template: "{{ .TemplateID }}"
type: Opaque
stringData:
  apiKey: "{{ .Values.apiKey }}"
{{- end }}
```

### Step 5: Set the execution order

In `podman/metadata.yaml`, apply the secret before the server pod.

```yaml
name: my-llm
version: "1.0.0"
podTemplateExecutions:
  - [my-llm-secret.yaml.tmpl]
  - [my-llm-server.yaml.tmpl]
```

### Step 6: Use the secret in the server pod

File: `podman/templates/my-llm-server.yaml.tmpl`. Do these things:

- Add the labels `ai-services.io/secret` and `ai-services.io/volume` with the secret name. Without them, the runtime does not delete the secret on teardown.
- Mount the secret as a volume.
- Read the key from the file at startup. Do not put the key into `env` as a literal value.
- Put the API port first. The engine uses the pod name as `.Values.llm.host` and the first `containerPort` of the first container as `.Values.llm.port`.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: "my-llm-{{ .InstanceSlug }}"
  labels:
    ai-services.io/template: "{{ .TemplateID }}"
    {{- if .Values.apiKey }}
    ai-services.io/secret: "my-llm-secret-{{ .InstanceSlug }}"
    ai-services.io/volume: "my-llm-secret-{{ .InstanceSlug }}"
    {{- end }}
spec:
  restartPolicy: always
  volumes:
    {{- if .Values.apiKey }}
    - name: my-llm-secret
      secret:
        secretName: "my-llm-secret-{{ .InstanceSlug }}"
    {{- end }}
  containers:
    - name: llm
      image: "{{ .Values.image }}"
      command: ["/bin/bash"]
      args:
        - "-c"
        - |
          {{- if .Values.apiKey }}
          export MY_LLM_API_KEY=$(cat /etc/secret/my-llm-secret/apiKey)
          {{- end }}
          exec <server start command> --model {{ .Values.model }} --port 8000
      ports:
        - containerPort: 8000
      volumeMounts:
        {{- if .Values.apiKey }}
        - mountPath: /etc/secret/my-llm-secret
          name: my-llm-secret
          readOnly: true
        {{- end }}
```

Replace `MY_LLM_API_KEY` with the variable your server reads (for example, vLLM reads `VLLM_API_KEY`). Your server must reject requests without a valid key. If it does not, the key gives no protection.

## Procedure: service

The service declares the LLM as a dependency in its top-level `metadata.yaml`:

```yaml
dependencies:
  - id: llm
```

In the service pod template, build the secret name from `.Values.llm.instanceSlug`, mount the secret and read the key from the file. The volume name and mount path belong to the service pod. You can choose them freely.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: "my-service-{{ .InstanceSlug }}"
  labels:
    ai-services.io/template: "{{ .TemplateID }}"
spec:
  restartPolicy: always
  volumes:
    {{- if .Values.llm.apiKey }}
    - name: llm-secret
      secret:
        secretName: "my-llm-secret-{{ .Values.llm.instanceSlug }}"
    {{- end }}
  containers:
    - name: my-service
      image: "{{ .Values.myservice.image }}"
      command: ["/bin/sh", "-c"]
      args:
        - |
          {{- if .Values.llm.apiKey }}
          export LLM_API_KEY=$(cat /etc/secret/llm-secret/apiKey)
          {{- end }}
          exec <service start command>
      env:
        - name: LLM_ENDPOINT
          value: "http://{{ .Values.llm.host }}:{{ .Values.llm.port }}"
        - name: LLM_MODEL
          value: "{{ .Values.llm.model }}"
      volumeMounts:
        {{- if .Values.llm.apiKey }}
        - mountPath: /etc/secret/llm-secret
          name: llm-secret
          readOnly: true
        {{- end }}
```

Do not add the LLM secret to the service pod's `ai-services.io/secret` or `ai-services.io/volume` labels. The component owns the secret.

Reference: `ai-services/assets/services/summarize/podman/templates/summarize-api.yaml.tmpl`.

## Rules

- Use the same values field name on both sides. `apiKey` is recommended and required for the built-in services.
- Use the same secret name pattern and data key on both sides.
- Always put the instance slug in the secret name: `.InstanceSlug` in the component, `.Values.llm.instanceSlug` in the service.
- Keep the empty default `""`. All key logic depends on `if .Values.apiKey` / `if .Values.llm.apiKey`.
- Do not hardcode a key in `values.yaml`, in templates or in the bundle archive.
- Do not write `{{ .Values.apiKey }}` or `{{ .Values.llm.apiKey }}` into `env.value`. Use the secret only.
- Add the `ai-services.io/secret` and `ai-services.io/volume` labels on the component pod that owns the secret.

## Checklist

- [ ] Top-level `metadata.yaml` has `component_type: llm`.
- [ ] `podman/values.yaml` has `apiKey: ""` and all fields that the service reads.
- [ ] `podman/values.schema.json` exists and has `apiKey` with `"format": "password"`.
- [ ] Secret template creates `<component>-secret-{{ .InstanceSlug }}` with data key `apiKey`, only when `apiKey` is set.
- [ ] `podTemplateExecutions` applies the secret before the server pod.
- [ ] Server pod has `ai-services.io/secret` and `ai-services.io/volume` labels.
- [ ] Server pod reads the key from the mounted file, not from a literal env value.
- [ ] API port is the first `containerPort` of the first container.
- [ ] Service mounts `<component>-secret-{{ .Values.llm.instanceSlug }}` and reads the same data key.
- [ ] If the component must work with built-in services: secret is named `vllm-secret-{{ .InstanceSlug }}`.
- [ ] The server rejects requests without a valid key.
- [ ] Deploy test: with no key, the service connects without auth. With a key, the service connects and an unauthenticated `curl` to the LLM fails.
