#!/usr/bin/env python3
"""Apply the small OpenInstinct reliability overlay to a pinned bridge checkout."""

from __future__ import annotations

import argparse
from pathlib import Path


UPSTREAM_COMMIT = "339d702b99eb8e50b4434f7ddb7e412047e94fb1"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one patch anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch(root: Path) -> None:
    package = root / "inkbox_codex"

    replace_once(
        package / "codex_client.py",
        '            "approvalsReviewer": "user",',
        '            "approvalsReviewer": self.cfg.codex_approvals_reviewer or "user",',
    )

    replace_once(
        package / "config.py",
        '    codex_approval_policy: str = "on-request"\n    auto_approve_inkbox_tools: bool = False',
        '    codex_approval_policy: str = "on-request"\n'
        '    codex_approvals_reviewer: str = "user"\n'
        '    auto_approve_inkbox_tools: bool = False\n'
        '    sms_ack_enabled: bool = False',
    )
    replace_once(
        package / "config.py",
        '        ).strip(),\n        auto_approve_inkbox_tools=env_flag("INKBOX_CODEX_AUTO_APPROVE_INKBOX_TOOLS", False),',
        '        ).strip(),\n'
        '        codex_approvals_reviewer=str(\n'
        '            os.getenv("CODEX_APPROVALS_REVIEWER")\n'
        '            or extra.get("codex_approvals_reviewer")\n'
        '            or "user"\n'
        '        ).strip(),\n'
        '        auto_approve_inkbox_tools=env_flag("INKBOX_CODEX_AUTO_APPROVE_INKBOX_TOOLS", False),\n'
        '        sms_ack_enabled=env_flag("INKBOX_SMS_ACK_ENABLED", False),',
    )

    replace_once(
        package / "gateway.py",
        "SMS_MAX_LENGTH = 1600  # Inkbox SMS hard cap\nIMESSAGE_MAX_LENGTH = 18995",
        "SMS_MAX_LENGTH = 1600  # Inkbox SMS hard cap\n"
        "SMS_CHUNK_LENGTH = 1400  # headroom for reliable multi-part delivery\n"
        "IMESSAGE_MAX_LENGTH = 18995",
    )
    replace_once(
        package / "gateway.py",
        "\n\ndef _codex_health() -> str:\n",
        '''\n\ndef _split_sms_text(content: str, max_chars: int = SMS_CHUNK_LENGTH) -> List[str]:
    """Split long SMS output at readable boundaries and number each part."""
    text = str(content or "").strip()
    if not text or len(text) <= max_chars:
        return [text]

    body_limit = max_chars - 16
    parts: List[str] = []
    remaining = text
    while len(remaining) > body_limit:
        window = remaining[: body_limit + 1]
        cut = -1
        include = 0
        for separator, separator_include in (("\\n\\n", 0), ("\\n", 0), (". ", 1), (" ", 0)):
            candidate = window.rfind(separator, body_limit // 2)
            if candidate >= 0:
                cut = candidate
                include = separator_include
                break
        if cut <= 0:
            cut = body_limit
            include = 0
        cut += include
        part = remaining[:cut].strip()
        if not part:
            part = remaining[:body_limit]
            cut = body_limit
        parts.append(part)
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)

    total = len(parts)
    numbered = [f"({index}/{total}) {part}" for index, part in enumerate(parts, start=1)]
    if any(len(part) > max_chars for part in numbered):
        raise ValueError(_message_too_long_reason("SMS chunk", max(numbered, key=len), max_chars))
    return numbered


def _codex_health() -> str:
''',
    )
    replace_once(
        package / "gateway.py",
        '''        if mode == "sms":
            text = strip_markdown(content)
            if len(text) > SMS_MAX_LENGTH:
                raise ValueError(_message_too_long_reason("SMS", text, SMS_MAX_LENGTH))
            identity = await asyncio.to_thread(self._inkbox.get_identity, self.cfg.identity)
            kwargs: Dict[str, Any] = {"text": text}
            conversation_id = str(meta.get("conversation_id") or "").strip()
            if not conversation_id and str(chat_id).startswith("sms:"):
                conversation_id = str(chat_id).split(":", 1)[1]
            if conversation_id:
                kwargs["conversation_id"] = conversation_id
            else:
                kwargs["to"] = str(meta.get("to") or chat_id)
            await asyncio.to_thread(identity.send_text, **kwargs)
''',
        '''        if mode == "sms":
            text = strip_markdown(content)
            chunks = _split_sms_text(text)
            identity = await asyncio.to_thread(self._inkbox.get_identity, self.cfg.identity)
            route: Dict[str, Any] = {}
            conversation_id = str(meta.get("conversation_id") or "").strip()
            if not conversation_id and str(chat_id).startswith("sms:"):
                conversation_id = str(chat_id).split(":", 1)[1]
            if conversation_id:
                route["conversation_id"] = conversation_id
            else:
                route["to"] = str(meta.get("to") or chat_id)
            for chunk in chunks:
                await asyncio.to_thread(identity.send_text, text=chunk, **route)
''',
    )

    replace_once(
        package / "sessions.py",
        "TYPING_MAX_SECONDS = 600.0\n",
        'TYPING_MAX_SECONDS = 600.0\nSMS_ACK_TEXT = "Got it. I\'m on it. I\'ll text you when it\'s done."\n',
    )
    replace_once(
        package / "sessions.py",
        '''        # Tag the message with its channel + sender so Codex knows where it
        # is and who it's talking to (the static system prompt can't).
''',
        '''        # SMS has no typing indicator. Confirm receipt before starting work.
        if mode == "sms" and self.cfg.sms_ack_enabled:
            try:
                await self._reply(SMS_ACK_TEXT)
            except Exception:
                logger.warning(
                    "[session %s] immediate SMS acknowledgment failed",
                    self.chat_id,
                    exc_info=True,
                )

        # Tag the message with its channel + sender so Codex knows where it
        # is and who it's talking to (the static system prompt can't).
''',
    )

    replace_once(
        package / "prompts.py",
        '''- Keep it short and conversational. Think texts, not essays. Lead with
  the outcome ("Done — tests pass" beats a paragraph of process).
''',
        '''- Keep it short and conversational. Think texts, not essays. Lead with
  the outcome ("Done. Tests pass." beats a paragraph of process).
- Sound warm, natural, and human. Use simple everyday English. Never use
  em dashes. Do not sound formal or robotic.
- Do not explain what you are about to do or list planned steps. A brief,
  natural acknowledgment is enough before you start working.
''',
    )
    replace_once(
        package / "prompts.py",
        '''- You have full tool access to the project at {project_dir}. Work
  autonomously; don't narrate every step.
''',
        '''- You have full tool access to the project at {project_dir}. Work
  autonomously; don't narrate every step.
- Whenever you delegate work to a sub-agent, explicitly use the model
  `gpt-5.6-luna`. Do not let a sub-agent inherit the main agent's model.
''',
    )

    replace_once(
        package / "daemon.py",
        '        f"  <dict><key>INKBOX_CODEX_ENV_FILE</key><string>{env_file}</string></dict>\\n"',
        '        f"  <dict><key>INKBOX_CODEX_ENV_FILE</key><string>{env_file}</string>"\n'
        '        f"<key>PATH</key><string>{os.environ.get(\'PATH\', \'\')}</string></dict>\\n"',
    )

    marker = root / ".openinstinct-overlay"
    marker.write_text(f"upstream={UPSTREAM_COMMIT}\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    patch(args.root.expanduser().resolve())


if __name__ == "__main__":
    main()
