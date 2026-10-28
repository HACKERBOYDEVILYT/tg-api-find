
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.discover import (
    parse_markdown_catalog,
    record_key,
    safe_public_https_url,
)
from scripts.telegram_bot import handle


class DiscoveryTests(unittest.TestCase):

    def test_rejects_http(self):
        self.assertFalse(
            safe_public_https_url("http://example.com")
        )

    def test_rejects_credentials(self):
        self.assertFalse(
            safe_public_https_url(
                "https://user:pass@example.com"
            )
        )

    @patch(
        "scripts.discover.socket.getaddrinfo",
        return_value=[
            (None, None, None, None, ("127.0.0.1", 443))
        ],
    )
    def test_rejects_private_dns(self, _mock):
        self.assertFalse(
            safe_public_https_url("https://example.com")
        )

    def test_markdown_parser(self):
        source = (
            "| [Example](https://example.com/docs) "
            "| A demo API | No | Unknown |\n"
        )

        records = parse_markdown_catalog(source, "test")

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0]["documentation_url"],
            "https://example.com/docs"
        )
        self.assertIsNone(records[0]["base_url"])

    def test_record_key(self):
        self.assertEqual(
            record_key({
                "spec_url": "https://example.com/spec/"
            }),
            "https://example.com/spec"
        )

    def test_telegram_search(self):
        result = handle(
            "/search anime",
            [{
                "name": "Anime Metadata",
                "category": "Entertainment",
                "purpose": "Anime lookup",
            }],
            8,
        )

        self.assertIn("Anime Metadata", result)

    def test_unknown_command(self):
        result = handle("/wat", [], 8)
        self.assertIn("/help", result)


if __name__ == "__main__":
    unittest.main()
