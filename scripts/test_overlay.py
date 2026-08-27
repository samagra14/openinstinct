#!/usr/bin/env python3
"""Behavior checks for the OpenInstinct bridge overlay."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path


async def check_sms_delivery() -> None:
    from inkbox_codex import gateway
    from inkbox_codex.config import BridgeConfig

    class FakeIdentity:
        def __init__(self) -> None:
            self.sent: list[dict[str, str]] = []

        def send_text(self, **kwargs: str) -> None:
            self.sent.append(kwargs)

    class FakeInkbox:
        def __init__(self, identity: FakeIdentity) -> None:
            self.identity = identity

        def get_identity(self, _identity: str) -> FakeIdentity:
            return self.identity

    identity = FakeIdentity()
    bridge = gateway.InkboxGateway(
        BridgeConfig(require_signature=False, identity="codex")
    )
    bridge._inkbox = FakeInkbox(identity)
    message = ("A useful sentence with readable words. " * 100).strip()

    await bridge.send_to_contact(
        "sms:conversation-123",
        message,
        "sms",
        {},
    )

    assert len(identity.sent) > 1, "Long SMS output was not split"
    total = len(identity.sent)
    for index, delivery in enumerate(identity.sent, start=1):
        assert delivery["conversation_id"] == "conversation-123"
        assert delivery["text"].startswith(f"({index}/{total}) ")
        assert len(delivery["text"]) <= gateway.SMS_CHUNK_LENGTH


async def check_immediate_acknowledgment() -> None:
    from inkbox_codex.config import BridgeConfig
    from inkbox_codex.sessions import ContactSession, SMS_ACK_TEXT

    sent: list[tuple[str, str, str, dict[str, str]]] = []

    async def send_fn(
        chat_id: str,
        text: str,
        mode: str,
        meta: dict[str, str],
    ) -> None:
        sent.append((chat_id, text, mode, meta))

    session = ContactSession(
        "sms:conversation-123",
        BridgeConfig(sms_ack_enabled=True),
        send_fn,
        {},
        {},
    )
    blocker = asyncio.create_task(asyncio.Event().wait())
    session._worker = blocker
    try:
        await session.handle_inbound(
            "Please do this task",
            "sms",
            {"conversation_id": "conversation-123"},
        )
        assert sent == [
            (
                "sms:conversation-123",
                SMS_ACK_TEXT,
                "sms",
                {"conversation_id": "conversation-123"},
            )
        ], "SMS was not acknowledged before work was queued"
        assert session._queue.qsize() == 1
    finally:
        blocker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await blocker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root.expanduser().resolve()))
    asyncio.run(check_sms_delivery())
    asyncio.run(check_immediate_acknowledgment())
    print("overlay behavior verified")


if __name__ == "__main__":
    main()
