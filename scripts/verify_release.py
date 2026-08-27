#!/usr/bin/env python3
"""Check that the public release still matches its advertised behavior."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_BROWSER_INSTRUCTION = (
    "Use live web search for current information. Use a persistent browser profile at "
    "`browser-profile/` for interactive websites so login sessions survive restarts."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def run_configure(temp_root: Path) -> tuple[Path, Path, Path, Path]:
    project = temp_root / "workspace"
    codex_home = temp_root / "codex"
    env_file = temp_root / "state" / ".env"
    service = temp_root / "openinstinct.service"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "configure.py"),
            "--source",
            str(ROOT),
            "--codex-home",
            str(codex_home),
            "--project-dir",
            str(project),
            "--env-file",
            str(env_file),
            "--service-file",
            str(service),
            "--bridge-bin",
            str(temp_root / "bin" / "inkbox-codex"),
        ],
        check=True,
    )
    return project, codex_home, env_file, service


def main() -> None:
    install = (ROOT / "install.sh").read_text(encoding="utf-8")
    subprocess.run(["bash", "-n", str(ROOT / "install.sh")], check=True)

    browser_contract = {
        "AGENT_BROWSER_VERSION=\"0.35.1\"",
        "agent-browser-darwin-arm64",
        "agent-browser-darwin-x64",
        "agent-browser-linux-x64",
        "12be3313ec6d878d8fda62ca5c62b7013c1b6931bf57dd2678788654b01ffe95",
        "6cafdc32d0cccbd892310adb7a36d7cd97807ab684338664fc08c7fdfeb2fef2",
        "21874b7afbe12a225d01c7f3f7d635c2c2f740660f6ef5e7916737c60c4f1faf",
        "agent-browser install --with-deps",
        "agent-browser doctor --offline --quick",
        "open https://example.com",
        "localStorage.setItem('openinstinct_install_check', 'persisted')",
        "localStorage.getItem('openinstinct_install_check')",
    }
    for needle in browser_contract:
        require(needle in install, f"Missing browser install contract: {needle}")
    require("inkbox-codex\" doctor || true" not in install, "Final health check is still ignored")

    with tempfile.TemporaryDirectory(prefix="openinstinct-release-") as temporary:
        temporary_root = Path(temporary)
        existing_config = temporary_root / "codex" / "config.toml"
        existing_config.parent.mkdir(parents=True)
        existing_config.write_text('custom_setting = "keep me"\n', encoding="utf-8")
        project, codex_home, env_file, service = run_configure(temporary_root)
        backup = codex_home / "config.toml.pre-openinstinct"
        require(backup.exists(), "An existing Codex config was not backed up")
        require("keep me" in backup.read_text(encoding="utf-8"), "Codex config backup is incomplete")
        env = read_env(env_file)
        require(
            env.get("AGENT_BROWSER_PROFILE") == str((project / "browser-profile").resolve()),
            "Browser profile is not managed",
        )
        require(env.get("AGENT_BROWSER_CONTENT_BOUNDARIES") == "true", "Browser content boundaries are not enabled")
        require(env.get("CODEX_APPROVALS_REVIEWER") == "auto_review", "Auto-review is not enabled")
        require(env.get("INKBOX_SMS_ACK_ENABLED") == "true", "Immediate SMS acknowledgment is not enabled")
        require(Path(env.get("CODEX_BIN", "")).name == "codex", "Codex executable is not recorded")

        agents = (project / "AGENTS.md").read_text(encoding="utf-8")
        require("installed `agent-browser` CLI" in agents, "Agent is not told which browser executable to use")
        require("agent-browser open <url>" in agents, "Agent browser command convention is missing")
        require("agent-browser close" in agents, "Agent is not told to close finished browsers")
        require("gpt-5.6-luna" in agents, "Luna sub-agent default is missing")
        require("simple everyday English" in agents, "Conversational tone is missing")
        require("untrusted content" in agents, "Browser prompt-injection guidance is missing")

        config = (codex_home / "config.toml").read_text(encoding="utf-8")
        require('default_subagent_model = "gpt-5.6-luna"' in config, "Codex sub-agent model is wrong")
        require('approvals_reviewer = "auto_review"' in config, "Codex auto-review setting is wrong")

        unit = service.read_text(encoding="utf-8")
        require('Environment="PATH=' in unit, "Service does not preserve the executable path")
        require("Restart=on-failure" in unit, "Service restart policy is missing")

        custom = "\n\nKeep this custom operator preference.\n"
        legacy = agents.replace(
            next(
                paragraph
                for paragraph in agents.split("\n\n")
                if paragraph.startswith("Use live web search for current information.")
            ),
            LEGACY_BROWSER_INSTRUCTION,
        )
        (project / "AGENTS.md").write_text(legacy + custom, encoding="utf-8")
        run_configure(temporary_root)
        upgraded = (project / "AGENTS.md").read_text(encoding="utf-8")
        require(LEGACY_BROWSER_INSTRUCTION not in upgraded, "Legacy browser instruction was not upgraded")
        require(custom.strip() in upgraded, "A custom operator preference was overwritten")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    require("## Architecture" not in readme, "README brought back developer-first architecture")
    require("<video src=" in readme, "README launch video is missing")
    require("Use a real browser" in readme, "README browser capability is missing")
    require("Mac or Linux" in readme, "README local install option is missing")
    require("Recommended:** a small Intel/AMD Ubuntu" in readme, "README VM recommendation is missing")

    workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    require("scripts/test_overlay.py" in workflow, "CI does not exercise overlay behavior")

    print("release checks passed")


if __name__ == "__main__":
    main()
