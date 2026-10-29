
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
NEW_PATH = ROOT / "data" / "new-apis.json"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def main() -> int:
    if not TOKEN or not CHAT_ID:
        print(
            "Telegram secrets missing; skipping notifications.",
            flush=True,
        )
        return 0

    try:
        if not NEW_PATH.exists():
            print(f"No new API file found: {NEW_PATH}", flush=True)
            return 0

        records = json.loads(NEW_PATH.read_text(encoding="utf-8"))

        if not isinstance(records, list):
            print("ERROR: new-apis.json must contain a JSON list.")
            return 1

    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR reading new-apis.json: {exc}", flush=True)
        return 1

    if not records:
        print("No newly discovered APIs.", flush=True)
        return 0

    session = requests.Session()
    session.headers.update({
        "User-Agent": "PublicAPIExplorerBot/1.0"
    })

    sent = 0

    for index, item in enumerate(records[:30], start=1):
        if not isinstance(item, dict):
            print(f"Skipping invalid record #{index}.", flush=True)
            continue

        name = str(item.get("name") or "Unnamed API")[:200]
        category = str(item.get("category") or "Uncategorized")[:150]
        purpose = str(
            item.get("purpose") or "Description unavailable"
        )
        purpose = purpose.replace("<", "&lt;").replace(">", "&gt;")[:500]

        docs = str(
            item.get("documentation_url")
            or item.get("spec_url")
            or "Not available"
        )[:1000]

        message = (
            "🆕 New public API discovered\n\n"
            f"Name: {name}\n"
            f"Category: {category}\n"
            f"Purpose: {purpose}\n"
            f"Authentication: {item.get('auth') or 'Unknown'}\n"
            f"Pricing: {item.get('pricing') or 'Unknown'}\n"
            f"Docs: {docs}"
        )

        try:
            response = session.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )

            try:
                result = response.json()
            except ValueError:
                result = {}

            if not response.ok or not result.get("ok"):
                description = str(
                    result.get("description", "No Telegram error details")
                )
                print(
                    f"Telegram API error for record #{index}: "
                    f"HTTP {response.status_code}; {description}",
                    flush=True,
                )
                return 1

            sent += 1
            print(f"Notification sent: {name}", flush=True)

        except requests.RequestException as exc:
            # Do not print request URLs because they contain the bot token.
            print(
                f"Network/request error for record #{index}: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return 1

    print(f"Notifications sent: {sent}", flush=True)

    if len(records) > 30:
        print(
            f"Remaining records not sent: {len(records) - 30}",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
