
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
NEW_PATH = ROOT / "data" / "new-apis.json"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def main():
    if not TOKEN or not CHAT_ID:
        print("Telegram secrets missing; skipping notifications.")
        return 0

    try:
        records = (
            json.loads(NEW_PATH.read_text(encoding="utf-8"))
            if NEW_PATH.exists() else []
        )
    except (json.JSONDecodeError, OSError):
        print("Could not read new API records.")
        return 0

    if not records:
        print("No newly discovered APIs.")
        return 0

    session = requests.Session()
    session.headers.update({
        "User-Agent": "PublicAPIExplorerBot/1.0"
    })

    for item in records[:30]:
        name = str(item.get("name") or "Unnamed API")[:200]
        category = str(item.get("category") or "Uncategorized")[:150]
        purpose = str(
            item.get("purpose") or "Description unavailable"
        ).replace("<", "&lt;").replace(">", "&gt;")[:500]

        docs = (
            item.get("documentation_url")
            or item.get("spec_url")
            or "Not available"
        )

        message = (
            "🆕 New public API discovered\n\n"
            f"Name: {name}\n"
            f"Category: {category}\n"
            f"Purpose: {purpose}\n"
            f"Authentication: {item.get('auth') or 'Unknown'}\n"
            f"Pricing: {item.get('pricing') or 'Unknown'}\n"
            f"Docs: {docs}"
        )

        response = session.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": True
            },
            timeout=20
        )

        response.raise_for_status()

        if not response.json().get("ok"):
            raise RuntimeError("Telegram rejected the notification")

    if len(records) > 30:
        print(
            f"Sent 30 notifications out of {len(records)} new records."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
