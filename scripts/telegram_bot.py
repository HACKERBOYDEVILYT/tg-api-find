
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "public-apis.json"
OFFSET_PATH = ROOT / "data" / "telegram-offset.json"
CONFIG_PATH = ROOT / "config" / "settings.json"

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"

HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "PublicAPIExplorerBot/1.0"})
MAX_MESSAGE = 3900


def load_json(path, default):
    try:
        return (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists() else default
        )
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def telegram(method, payload):
    response = HTTP.post(
        f"{API}/{method}", json=payload, timeout=20
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {method}")

    return data.get("result")


def send(message, chat_id=None):
    target = str(chat_id or CHAT_ID)

    if not target:
        return

    while message:
        chunk = message[:MAX_MESSAGE]

        if len(message) > MAX_MESSAGE:
            split_at = chunk.rfind("\n")
            if split_at > 500:
                chunk = chunk[:split_at]

        telegram("sendMessage", {
            "chat_id": target,
            "text": chunk,
            "disable_web_page_preview": True
        })

        message = message[len(chunk):].lstrip("\n")


def clean(value, default="Not available"):
    value = str(value or "").strip()
    return value if value else default


def load_records():
    records = load_json(DATA_PATH, [])
    return records if isinstance(records, list) else []


def format_short(item, index):
    name = clean(item.get("name"), "Unnamed API")
    category = clean(item.get("category"), "Uncategorized")
    purpose = clean(item.get("purpose"), "No description")

    if len(purpose) > 180:
        purpose = purpose[:177] + "..."

    docs = item.get("documentation_url") or item.get("spec_url")

    return (
        f"{index}. {name}\n"
        f"Category: {category}\n"
        f"Purpose: {purpose}\n"
        f"Docs: {docs or 'Not available'}"
    )


def command_help():
    return (
        "🤖 Public API Explorer Bot\n\n"
        "/list — Browse collected APIs\n"
        "/list 2 — Open page 2\n"
        "/search anime — Search APIs\n"
        "/details 1 — View API details\n"
        "/stats — Collection statistics\n"
        "/help — Show commands\n\n"
        "API availability, pricing and authentication "
        "must be verified with the provider."
    )


def list_page(page, records, page_size):
    if not records:
        return "No APIs collected yet. Run the GitHub Actions workflow first."

    page = max(1, page)
    total_pages = max(1, (len(records) + page_size - 1) // page_size)
    page = min(page, total_pages)

    start = (page - 1) * page_size
    lines = [
        f"📚 API Collection — Page {page}/{total_pages}",
        f"Total records: {len(records)}",
        ""
    ]

    for index, item in enumerate(
        records[start:start + page_size], start=start + 1
    ):
        lines.extend([format_short(item, index), ""])

    if page < total_pages:
        lines.append(f"Next page: /list {page + 1}")

    lines.append("Use /details ID to view full details.")
    return "\n".join(lines)


def search_records(query, records, page_size):
    query = query.strip().lower()

    if not query:
        return "Usage: /search anime"

    matches = []

    for index, item in enumerate(records, start=1):
        searchable = " ".join(
            str(item.get(key) or "")
            for key in (
                "name", "category", "purpose",
                "documentation_url", "spec_url", "base_url"
            )
        ).lower()

        if query in searchable:
            matches.append((index, item))

    if not matches:
        return f"No matches for: {query}\nTry /search data"

    lines = [f"🔎 Search results: {len(matches)} match(es)\n"]

    for index, item in matches[:page_size]:
        lines.extend([format_short(item, index), ""])

    if len(matches) > page_size:
        lines.append(
            f"Showing {page_size} results. Refine your search."
        )

    return "\n".join(lines)


def details(record_id, records):
    if record_id < 1 or record_id > len(records):
        return f"ID must be between 1 and {len(records)}. Use /list."

    item = records[record_id - 1]
    endpoints = item.get("endpoints") or []
    endpoint_lines = []

    for endpoint in endpoints[:15]:
        endpoint_lines.append(
            f"• {clean(endpoint.get('method'), '?')} "
            f"{clean(endpoint.get('path'), '/')}"
            + (
                f" — {endpoint['summary']}"
                if endpoint.get("summary") else ""
            )
        )

    if len(endpoints) > 15:
        endpoint_lines.append(
            f"…and {len(endpoints) - 15} more endpoints"
        )

    return (
        f"🧾 API Details — ID {record_id}\n\n"
        f"Name: {clean(item.get('name'))}\n"
        f"Category: {clean(item.get('category'))}\n"
        f"Purpose: {clean(item.get('purpose'))}\n"
        f"Authentication: {clean(item.get('auth'), 'Unknown')}\n"
        f"Pricing: {clean(item.get('pricing'), 'Unknown')}\n"
        f"Base URL: {clean(item.get('base_url'))}\n"
        f"Documentation: {clean(item.get('documentation_url'))}\n"
        f"Specification: {clean(item.get('spec_url'))}\n"
        f"Source: {clean(item.get('source'))}\n"
        f"Profile status: {clean(item.get('profile_status'))}\n\n"
        f"Endpoints ({len(endpoints)} found):\n"
        + (
            "\n".join(endpoint_lines)
            if endpoint_lines
            else "No endpoint list available."
        )
        + "\n\nMetadata does not guarantee availability or free usage."
    )


def stats(records):
    counts = {}

    for item in records:
        category = clean(item.get("category"), "Uncategorized")
        counts[category] = counts.get(category, 0) + 1

    top = sorted(
        counts.items(),
        key=lambda pair: (-pair[1], pair[0].lower())
    )[:15]

    lines = [
        "📊 API Collection Stats",
        f"Total records: {len(records)}",
        f"Categories: {len(counts)}",
        ""
    ]

    lines.extend(f"• {name}: {count}" for name, count in top)
    return "\n".join(lines)


def handle(text, records, page_size):
    parts = text.strip().split(maxsplit=1)
    command = parts[0].split("@")[0].lower() if parts else ""
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command in ("/start", "/help"):
        return command_help()

    if command == "/list":
        try:
            page = int(argument) if argument else 1
        except ValueError:
            page = 1
        return list_page(page, records, page_size)

    if command == "/search":
        return search_records(argument, records, page_size)

    if command == "/details":
        if not re.fullmatch(r"\d+", argument):
            return "Usage: /details 1"
        return details(int(argument), records)

    if command == "/stats":
        return stats(records)

    return "Unknown command. Send /help."


def main():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN is not configured.")
        return 0

    config = load_json(CONFIG_PATH, {})
    page_size = max(
        1, min(15, int(config.get("telegram_page_size", 8)))
    )

    records = load_records()
    offset_data = load_json(OFFSET_PATH, {"offset": 0})
    offset = int(offset_data.get("offset", 0))

    try:
        updates = telegram("getUpdates", {
            "offset": offset,
            "timeout": 0,
            "allowed_updates": ["message"]
        }) or []
    except Exception as exc:
        print(f"Telegram polling failed: {type(exc).__name__}")
        return 0

    highest_update = offset - 1

    for update in updates:
        update_id = int(update.get("update_id", 0))
        highest_update = max(highest_update, update_id)

        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text") or ""

        if not chat_id or not text.startswith("/"):
            continue

        if CHAT_ID and str(chat_id) != CHAT_ID:
            continue

        try:
            answer = handle(text, records, page_size)
            send(answer, chat_id)
        except Exception as exc:
            print(f"Command failed: {type(exc).__name__}")

    if highest_update >= offset:
        save_json(OFFSET_PATH, {"offset": highest_update + 1})

    return 0


if __name__ == "__main__":
    raise SystemExit(main)
