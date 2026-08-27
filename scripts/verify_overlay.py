#!/usr/bin/env python3
"""Fast structural checks for an overlaid bridge checkout."""

from __future__ import annotations

import argparse
import compileall
from pathlib import Path


EXPECTED = {
    "inkbox_codex/codex_client.py": "self.cfg.codex_approvals_reviewer",
    "inkbox_codex/config.py": "INKBOX_SMS_ACK_ENABLED",
    "inkbox_codex/daemon.py": "<key>PATH</key>",
    "inkbox_codex/gateway.py": "def _split_sms_text",
    "inkbox_codex/prompts.py": "gpt-5.6-luna",
    "inkbox_codex/sessions.py": "SMS_ACK_TEXT",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    for relative, needle in EXPECTED.items():
        text = (root / relative).read_text(encoding="utf-8")
        if needle not in text:
            raise SystemExit(f"Missing overlay marker {needle!r} in {relative}")
    if not compileall.compile_dir(root / "inkbox_codex", quiet=1):
        raise SystemExit("Bridge source did not compile")
    print("overlay verified")


if __name__ == "__main__":
    main()
