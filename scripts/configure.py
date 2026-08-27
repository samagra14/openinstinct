#!/usr/bin/env python3
"""Write OpenInstinct-owned configuration without printing secrets."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


MANAGED_ENV = {
    "AGENT_BROWSER_CONTENT_BOUNDARIES": "true",
    "AGENT_BROWSER_PROFILE": None,
    "CODEX_PROJECT_DIR": None,
    "CODEX_HOME": None,
    "CODEX_MODEL": "gpt-5.6-sol",
    "CODEX_SANDBOX": "workspace-write",
    "CODEX_APPROVAL_POLICY": "on-request",
    "CODEX_APPROVALS_REVIEWER": "auto_review",
    "CODEX_BIN": None,
    "INKBOX_CODEX_AUTO_APPROVE_INKBOX_TOOLS": "true",
    "INKBOX_SMS_ACK_ENABLED": "true",
}

LEGACY_BROWSER_INSTRUCTION = (
    "Use live web search for current information. Use a persistent browser profile at "
    "`browser-profile/` for interactive websites so login sessions survive restarts."
)


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def unit_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")


def upsert_env(path: Path, values: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    output: list[str] = []
    for line in existing:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else ""
        if key in pending:
            output.append(f"{key}={pending.pop(key)}")
        else:
            output.append(line)
    if output and output[-1]:
        output.append("")
    output.extend(f"{key}={value}" for key, value in pending.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    path.chmod(0o600)


def write_service(path: Path, *, bridge_bin: Path, env_file: Path, codex_home: Path, project_dir: Path) -> None:
    process_path = os.environ.get("PATH", "")
    content = f"""[Unit]
Description=OpenInstinct personal agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=\"INKBOX_CODEX_ENV_FILE={unit_escape(str(env_file))}\"
Environment=\"CODEX_HOME={unit_escape(str(codex_home))}\"
Environment=\"PATH={unit_escape(process_path)}\"
WorkingDirectory=\"{unit_escape(str(project_dir))}\"
ExecStart=\"{unit_escape(str(bridge_bin))}\" run
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o644)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--service-file", type=Path)
    parser.add_argument("--bridge-bin", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    codex_home = args.codex_home.expanduser().resolve()
    project_dir = args.project_dir.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve()

    codex_home.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "scratch").mkdir(exist_ok=True)
    (project_dir / "browser-profile").mkdir(exist_ok=True)

    agent_target = project_dir / "AGENTS.md"
    agent_source = (source / "config" / "AGENTS.md").read_text(encoding="utf-8")
    if not agent_target.exists():
        shutil.copy2(source / "config" / "AGENTS.md", agent_target)
    else:
        existing_agents = agent_target.read_text(encoding="utf-8")
        if LEGACY_BROWSER_INSTRUCTION in existing_agents:
            browser_instruction = next(
                paragraph
                for paragraph in agent_source.split("\n\n")
                if paragraph.startswith("Use live web search for current information.")
            )
            agent_target.write_text(
                existing_agents.replace(LEGACY_BROWSER_INSTRUCTION, browser_instruction),
                encoding="utf-8",
            )

    template = (source / "config" / "codex-config.toml").read_text(encoding="utf-8")
    rendered = template.replace("__PROJECT_DIR__", toml_escape(str(project_dir)))
    config_path = codex_home / "config.toml"
    config_backup = codex_home / "config.toml.pre-openinstinct"
    if config_path.exists() and not config_backup.exists():
        shutil.copy2(config_path, config_backup)
        config_backup.chmod(0o600)
    config_path.write_text(rendered, encoding="utf-8")
    config_path.chmod(0o600)

    values = {key: value for key, value in MANAGED_ENV.items() if value is not None}
    values["CODEX_PROJECT_DIR"] = str(project_dir)
    values["CODEX_HOME"] = str(codex_home)
    values["CODEX_MODEL"] = args.model
    values["CODEX_BIN"] = shutil.which("codex") or "codex"
    values["AGENT_BROWSER_PROFILE"] = str(project_dir / "browser-profile")
    upsert_env(env_file, values)

    if args.service_file:
        if not args.bridge_bin:
            parser.error("--bridge-bin is required with --service-file")
        write_service(
            args.service_file.expanduser().resolve(),
            bridge_bin=args.bridge_bin.expanduser().resolve(),
            env_file=env_file,
            codex_home=codex_home,
            project_dir=project_dir,
        )


if __name__ == "__main__":
    main()
