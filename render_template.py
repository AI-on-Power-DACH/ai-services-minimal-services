#!/usr/bin/env python3
"""
With this script the `ai-services` specific template for 
podman deployments. This scripts takes the root directory
from the 

Convert Go-template based Podman/Kube pod templates (e.g. proxy-api.yaml.tmpl)
and values.yaml into a runnable Podman/Kubernetes pod specification.

Usage:
    python3 render_template.py [TEMPLATE_PATH] [-f VALUES_PATH] [-o OUTPUT_PATH] [--run]

Requirements:
    - pyyaml: For yaml parsing of the metadata and values files.

Examples:
    # Render default template to stdout:
    python3 render_template.py

    # Render with custom values and save to file:
    python3 render_template.py podman/templates/proxy-api.yaml.tmpl \
        -f podman/values.yaml \
        --set cloud_url="https://api.openai.com/v1" \
        --set cloud_api_key="sk-..." \
        -o pod-spec.yaml

    # Render and run immediately with Podman:
    python3 render_template.py --run --set cloud_api_key="sk-..."
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
import yaml
import jinja2


__version__ = "1.1.0"
__author__ = "Markus Mielimonka<markus.mielimonka@ibm.com>"


def parse_simple_yaml(content: str) -> dict:
    """Parse standard flat/nested YAML without external dependencies."""
    return yaml.safe_load(content) or {}

def go_template_to_jinja(tmpl: str) -> str:
    """Translate basic Go template conditionals and variable syntax to Jinja2."""

    # 1. {{ - if and .A .B }}
    def repl_if_and(m):
        ltrim = "-" if m.group(1) else ""
        rtrim = "-" if m.group(4) else ""
        a = m.group(2).lstrip(".")
        b = m.group(3).lstrip(".")
        return f"{{%{ltrim} if {a} and {b} %{rtrim}}}"

    tmpl = re.sub(
        r"\{\{(-)?\s*if\s+and\s+(\.[\w\.]+)\s+(\.[\w\.]+)\s*(-)?\}\}",
        repl_if_and,
        tmpl,
    )

    # 2. {{ - else if .A }}
    def repl_elif(m):
        ltrim = "-" if m.group(1) else ""
        rtrim = "-" if m.group(3) else ""
        a = m.group(2).lstrip(".")
        return f"{{%{ltrim} elif {a} %{rtrim}}}"

    tmpl = re.sub(
        r"\{\{(-)?\s*else\s+if\s+(\.[\w\.]+)\s*(-)?\}\}", repl_elif, tmpl
    )

    # 3. {{ - if .A }}
    def repl_if(m):
        ltrim = "-" if m.group(1) else ""
        rtrim = "-" if m.group(3) else ""
        a = m.group(2).lstrip(".")
        return f"{{%{ltrim} if {a} %{rtrim}}}"

    tmpl = re.sub(r"\{\{(-)?\s*if\s+(\.[\w\.]+)\s*(-)?\}\}", repl_if, tmpl)

    # 4. {{ - else }}
    tmpl = re.sub(r"\{\{(-)?\s*else\s*(-)?\}\}", r"{%\1 else %\2}", tmpl)

    # 5. {{ - end }}
    tmpl = re.sub(r"\{\{(-)?\s*end\s*(-)?\}\}", r"{%\1 endif %\2}", tmpl)

    # 6. {{ .Values.X }} / {{ .InstanceSlug }} / etc.
    def repl_var(m):
        ltrim = "-" if m.group(1) else ""
        rtrim = "-" if m.group(3) else ""
        var = m.group(2).lstrip(".")
        return f"{{{{{ltrim} {var} {rtrim}}}}}"

    tmpl = re.sub(r"\{\{(-)?\s*(\.[\w\.]+)\s*(-)?\}\}", repl_var, tmpl)

    return tmpl


def extract_ports(yaml_text: str) -> list[int]:
    """Collect unique container/route ports from rendered YAML documents."""
    ports: list[int] = []
    # Match containerPort: 8080
    for match in re.findall(r"containerPort:\s*[\"']?(\d+)[\"']?", yaml_text):
        port = int(match)
        if port not in ports:
            ports.append(port)
    # Match routes annotations e.g. "8080:..."
    for match in re.findall(r"ai-services\.io/routes:\s*[\"']?(\d+):", yaml_text):
        port = int(match)
        if port not in ports:
            ports.append(port)
    return ports


def render_template(
    template_str: str,
    values: dict,
    instance_slug: str = "test",
    template_id: str = "cloud-llm",
) -> str:
    """Render the template string using Jinja2."""

    jinja_template = go_template_to_jinja(template_str)
    env = jinja2.Environment()
    template = env.from_string(jinja_template)

    context = {
        "InstanceSlug": instance_slug,
        "TemplateID": template_id,
        "Values": values,
    }
    return template.render(**context)

def parse_arguments()-> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render .yaml.tmpl pod and secret templates into a runnable Podman/Kubernetes specification."
    )
    parser.add_argument(
        "template",
        nargs="?",
        default=None,
        help="Path to the root folder of the ai-services component/service.",
    )
    run_args = parser.add_argument_group("Running",
                                         "Arguments used only when the parsed/created spec is directly run via the --run arg.")
    
    parser.add_argument(
        "-m",
        "--metadata",
        default="podman/metadata.yaml",
        help="Path to podman metadata.yaml file (default: podman/metadata.yaml)",
    )
    parser.add_argument(
        "-f",
        "--values",
        default="podman/values.yaml",
        help="Path to values.yaml file (default: podman/values.yaml)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-s",
        "--slug",
        default="local-test",
        help="Instance slug value (default: local-test)",
    )
    parser.add_argument(
        "-t",
        "--template-id",
        default="cloud-llm-proxy",
        help="Template ID value (default: cloud-llm-proxy)",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help="Override values (key=value, e.g. --set cloud_url=https://api.openai.com/v1)",
    )
    run_args.add_argument(
        "-p",
        "--publish",
        action="append",
        default=[],
        help="Explicit port publish mappings (e.g. -p 8080:8080). If omitted with --run, auto-publishes template ports.",
    )
    run_args.add_argument(
        "--run",
        action="store_true",
        help="Run the generated specification using 'podman play kube' with auto-published ports",
    )

    args = parser.parse_args()
    if args.publish and not args.run:
        print(Warning("[Warning] Some ports are set to publish but no execution with --run."), file=sys.stderr)
    return args

def main():
    
    args = parse_arguments()
    values_path = Path(args.values)
    values = {}
    if values_path.is_file():
        values = parse_simple_yaml(values_path.read_text(encoding="utf-8"))

    # Apply --set overrides
    for item in args.set:
        if "=" in item:
            k, v = item.split("=", 1)
            values[k.strip()] = v.strip()

    # Determine templates to render
    if args.template:
        template_files = [Path(args.template)]
    else:
        # Discover templates from podman/metadata.yaml if present
        metadata_path = Path(args.metadata)
        template_files = []
        if metadata_path.is_file():
            meta_text = metadata_path.read_text(encoding="utf-8")
            templates_dir = metadata_path.parent / "templates"
            # Extract list from podTemplateExecutions
            tmpl_names = []
            data = yaml.safe_load(meta_text) or {}
            for execution in data.get("podTemplateExecutions", []):
                if isinstance(execution, list):
                    tmpl_names.extend(execution)
                elif isinstance(execution, str):
                    tmpl_names.append(execution)

            for name in tmpl_names:
                candidate = templates_dir / name
                if candidate.is_file():
                    template_files.append(candidate)

        print(f"Found template file: {template_files}")
        # Fallback if metadata didn't yield templates
        if not template_files:
            templates_dir = Path("podman/templates")
            if templates_dir.is_dir():
                template_files = sorted(templates_dir.glob("*.yaml.tmpl"))

    docs = []
    for tmpl_path in template_files:
        if not tmpl_path.is_file():
            print(f"Error: Template file not found: {tmpl_path}", file=sys.stderr)
            sys.exit(1)
        content = tmpl_path.read_text(encoding="utf-8")
        rendered_doc = render_template(
            template_str=content,
            values=values,
            instance_slug=args.slug,
            template_id=args.template_id,
        )
        if rendered_doc.strip():
            docs.append(rendered_doc.strip())

    print(f"used {len(docs)} docs.")
    combined = "\n---\n".join(docs) + "\n"

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(combined, encoding="utf-8")
        print(f"Rendered pod specification written to {out_path}")
    else:
        if not args.run:
            print(combined)

    if args.run:
        target_file = args.output or f"/tmp/podman-{args.slug}.yaml"
        if not args.output:
            Path(target_file).write_text(combined, encoding="utf-8")

        # Determine ports to publish
        publish_args: list[str] = []
        if args.publish:
            for p in args.publish:
                publish_args.extend(["--publish", p])
        else:
            # Auto-discover ports from rendered spec
            discovered_ports = extract_ports(combined)
            for p in discovered_ports:
                publish_args.extend(["--publish", f"{p}:{p}"])

        cmd = ["podman", "play", "kube", *publish_args, target_file]
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd)
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
