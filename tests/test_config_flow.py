"""Tests for Mijn Liander config flow error handling and translations."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from custom_components.mijn_liander.config_flow import _map_http_error, _validate_input

INTEGRATION_PATH = Path(__file__).parents[1] / "custom_components" / "mijn_liander"


class TestConfigFlowErrors(unittest.TestCase):
    """Test config flow error mappings and translation completeness."""

    def test_map_http_error_codes(self) -> None:
        """HTTP error status codes map to expected Home Assistant error keys."""
        mappings = {
            401: "invalid_auth",
            403: "forbidden",
            404: "not_found",
            429: "too_many_requests",
            503: "service_unavailable",
            500: "unknown",
        }
        for status_code, expected_key in mappings.items():
            error = aiohttp.ClientResponseError(
                request_info=None, history=(), status=status_code
            )
            self.assertEqual(_map_http_error(error), expected_key)

    def test_validate_input_network_error(self) -> None:
        """ClientError during validation maps to cannot_connect."""
        mock_session = MagicMock()
        mock_session.post.side_effect = aiohttp.ClientError()
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        async def run_test():
            with patch("aiohttp.ClientSession", return_value=mock_session_cm):
                return await _validate_input("user@example.com", "secret", 5)

        res = asyncio.run(run_test())
        self.assertEqual(res, {"status": "error", "error": "cannot_connect"})

    def test_config_error_translations_match(self) -> None:
        """Every config error key in source strings exists in locales."""
        source = json.loads((INTEGRATION_PATH / "strings.json").read_text())
        locales = {
            lang: json.loads((INTEGRATION_PATH / "translations" / f"{lang}.json").read_text())
            for lang in ("en", "nl")
        }

        source_errors = set(source["config"]["error"].keys())
        self.assertIn("cannot_connect", source_errors)
        self.assertIn("forbidden", source_errors)
        self.assertIn("not_found", source_errors)
        self.assertIn("invalid_auth", source_errors)
        self.assertIn("service_unavailable", source_errors)

        for lang, locale in locales.items():
            locale_errors = set(locale["config"]["error"].keys())
            self.assertEqual(source_errors, locale_errors, f"Error mismatch in {lang}")


if __name__ == "__main__":
    unittest.main()
