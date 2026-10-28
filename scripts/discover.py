
from __future__ import annotations

import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "settings.json"
STORE_PATH = ROOT / "data" / "public-apis.json"
NEW_PATH = ROOT / "data" / "new-apis.json"
REPORT_PATH = ROOT / "data" / "scan-report.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PublicAPIExplorerBot/1.0",
    "Accept": "application/json, text/plain, */*",
})


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON file: {path}"
        ) from exc


def safe_public_https_url(url, allowed_hosts=None):
    try:
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        if parsed.port not in (None, 443):
            return False

        host = parsed.hostname.rstrip(".").lower()

        if allowed_hosts is not None and host not in allowed_hosts:
            return False

        answers = socket.getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )

        if not answers:
            return False

        for answer in answers:
            ip = ipaddress.ip_address(answer[4][0])
            if not ip.is_global:
                return False

        return True

    except (ValueError, OSError, socket.gaierror):
        return False


def fetch(url, timeout, max_bytes, allowed_hosts=None):
    if not safe_public_https_url(url, allowed_hosts):
        raise ValueError("URL rejected by HTTPS/public-host validation")

    with SESSION.get(
        url,
        timeout=timeout,
        stream=True,
        allow_redirects=False
    ) as response:
        response.raise_for_status()

        chunks = []
        total = 0

        for chunk in response.iter_content(chunk_size=16384):
            if not chunk:
                continue

            total += len(chunk)

            if total > max_bytes:
                raise ValueError("Response size limit exceeded")

            chunks.append(chunk)

        return b"".join(chunks)


def normalise(item):
    for key in (
        "name", "category", "purpose",
        "documentation_url", "spec_url", "base_url"
    ):
        item[key] = str(item.get(key) or "").strip() or None

    item.setdefault("auth", "Unknown")
    item.setdefault("pricing", "Unknown")
    item.setdefault("endpoints", [])
    item.setdefault("source", "Unknown")
    item.setdefault("profile_status", "metadata_only")
    item.setdefault("first_seen", utc_now())
    item["last_seen"] = utc_now()

    return item


def parse_markdown_catalog(text, source_name):
    records = []
    category = "Uncategorized"

    for line in text.splitlines():
        heading = re.match(r"^#{2,4}\s+(.+?)\s*#*\s*$", line)

        if heading:
            category = heading.group(1).strip()
            continue

        if not line.strip().startswith("|") or "---" in line:
            continue

        cells = [
            cell.strip()
            for cell in line.strip().strip("|").split("|")
        ]

        if len(cells) < 2:
            continue

        match = re.search(
            r"\[([^\]]+)\]\((https://[^)]+)\)",
            cells[0]
        )

        if not match:
            continue

        name = match.group(1).strip()
        docs = match.group(2).strip()
        description = re.sub(r"<[^>]+>", "", cells[1]).strip()

        auth = cells[2].strip() if len(cells) > 2 else "Unknown"

        records.append(normalise({
            "name": name,
            "category": category,
            "purpose": description or "Description unavailable",
            "documentation_url": docs,
            "spec_url": None,
            "base_url": None,
            "auth": auth or "Unknown",
            "pricing": "Unknown",
            "endpoints": [],
            "source": source_name,
            "profile_status": "metadata_only"
        }))

    return records


def parse_apisguru(data, source_name):
    records = []

    if not isinstance(data, dict):
        return records

    for api_id, entry in data.items():
        if not isinstance(entry, dict):
            continue

        versions = entry.get("versions") or {}
        preferred = entry.get("preferred")
        version = versions.get(preferred) if preferred else None

        if not isinstance(version, dict):
            version = next(
                (v for v in versions.values() if isinstance(v, dict)),
                {}
            )

        info = version.get("info") or {}

        if not isinstance(info, dict):
            info = {}

        origin = info.get("x-origin")
        docs = None

        if isinstance(origin, list) and origin:
            first = origin[0]
            if isinstance(first, dict):
                docs = first.get("url")

        records.append(normalise({
            "name": info.get("title") or api_id,
            "category": "API Specification",
            "purpose": info.get("description") or
                       "OpenAPI/Swagger metadata available",
            "documentation_url": docs,
            "spec_url": version.get("swaggerUrl") or
                        version.get("openapiUrl"),
            "base_url": None,
            "auth": "Unknown",
            "pricing": "Unknown",
            "endpoints": [],
            "source": source_name,
            "source_id": api_id,
            "version": version.get("version") or preferred,
            "profile_status": "metadata_only"
        }))

    return records


def enrich_openapi(item, config):
    spec_url = item.get("spec_url")

    if not spec_url:
        return item

    try:
        body = fetch(
            spec_url,
            int(config.get("timeout_seconds", 20)),
            int(config.get("max_response_bytes", 2000000)),
            allowed_hosts={"api.apis.guru"}
        )

        spec = json.loads(body.decode("utf-8"))
        info = spec.get("info") or {}

        item["purpose"] = (
            info.get("description") or item.get("purpose")
        )

        servers = spec.get("servers") or []

        if servers and isinstance(servers[0], dict):
            item["base_url"] = servers[0].get("url")

        schemes = (
            spec.get("components", {}).get("securitySchemes")
            or spec.get("securityDefinitions")
            or {}
        )

        if schemes:
            item["auth"] = ", ".join(sorted(schemes.keys()))
        elif spec.get("security"):
            item["auth"] = "Security requirement declared"
        else:
            item["auth"] = (
                "No global security requirement declared; "
                "check endpoint-level security"
            )

        endpoints = []

        for path, methods in (spec.get("paths") or {}).items():
            if not isinstance(methods, dict):
                continue

            for method, operation in methods.items():
                if method.lower() not in {
                    "get", "post", "put", "patch",
                    "delete", "options", "head"
                }:
                    continue

                if not isinstance(operation, dict):
                    continue

                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary")
                                or operation.get("description")
                                or ""
                })

                if len(endpoints) >= 100:
                    break

            if len(endpoints) >= 100:
                break

        item["endpoints"] = endpoints
        item["profile_status"] = "openapi_parsed"

        item.pop("profile_error", None)

    except Exception as exc:
        item["profile_status"] = "metadata_only"
        item["profile_error"] = type(exc).__name__

    return item


def record_key(item):
    value = (
        item.get("spec_url")
        or item.get("documentation_url")
        or f"{item.get('source')}::{item.get('name')}"
    )

    return value.strip().lower().rstrip("/")


def main():
    config = load_json(CONFIG_PATH, {})
    existing_list = load_json(STORE_PATH, [])

    if not isinstance(existing_list, list):
        raise RuntimeError("API store must be a JSON array")

    existing = {
        record_key(item): item
        for item in existing_list
        if isinstance(item, dict)
    }

    discovered = []
    source_results = []

    timeout = int(config.get("timeout_seconds", 20))
    max_bytes = int(config.get("max_response_bytes", 2000000))

    for source in config.get("sources", []):
        try:
            body = fetch(
                source["url"], timeout, max_bytes
            )

            if source["type"] == "markdown":
                rows = parse_markdown_catalog(
                    body.decode("utf-8", errors="replace"),
                    source["name"]
                )
            elif source["type"] == "apisguru":
                rows = parse_apisguru(
                    json.loads(body.decode("utf-8")),
                    source["name"]
                )
            else:
                raise ValueError("Unsupported catalog type")

            discovered.extend(rows)

            source_results.append({
                "source": source["name"],
                "status": "success",
                "records": len(rows)
            })

        except Exception as exc:
            source_results.append({
                "source": source.get("name", "Unknown"),
                "status": "failed",
                "error": type(exc).__name__
            })

    if not any(
        result["status"] == "success"
        for result in source_results
    ):
        raise RuntimeError(
            "All API catalog sources failed: "
            + json.dumps(source_results)
        )

    new_keys = []
    max_new = int(config.get("max_new_per_run", 1000))

    for item in discovered:
        key = record_key(item)

        if key in existing:
            old = existing[key]
            item["first_seen"] = old.get(
                "first_seen", item["first_seen"]
            )

            for field in (
                "base_url", "endpoints", "profile_status", "auth"
            ):
                if (
                    not item.get(field)
                    or item.get(field) in (
                        [], "Unknown", "metadata_only"
                    )
                ) and old.get(field):
                    item[field] = old[field]

            existing[key] = {**old, **item}

        elif len(new_keys) < max_new:
            existing[key] = item
            new_keys.append(key)

    budget = max_new

    for key, item in list(existing.items()):
        if (
            item.get("spec_url")
            and item.get("profile_status") != "openapi_parsed"
            and budget > 0
        ):
            existing[key] = enrich_openapi(item, config)
            budget -= 1

    limit = int(config.get("max_records", 20000))

    items = sorted(
        existing.values(),
        key=lambda item: (item.get("name") or "").lower()
    )[:limit]

    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    STORE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    NEW_PATH.write_text(
        json.dumps(
            [existing[key] for key in new_keys],
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    report = {
        "scanned_at": utc_now(),
        "total_records": len(items),
        "new_records": len(new_keys),
        "sources": source_results
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
