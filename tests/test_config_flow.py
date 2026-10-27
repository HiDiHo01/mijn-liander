"""Tests for Mijn Liander config flow error handling and translations."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from custom_components.mijn_liander.config_flow import (
    ConfigFlow,
    _map_http_error,
    _validate_input,
)

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
                return await _validate_input("user@example.com", "secret")

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

    def test_config_flow_schema_selectors(self) -> None:
        """Config flow schema uses EMAIL and PASSWORD selectors with autocomplete attributes."""
        from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
        from homeassistant.helpers.selector import TextSelectorType

        from custom_components.mijn_liander.config_flow import STEP_USER_DATA_SCHEMA

        username_selector = None
        password_selector = None

        for key, selector in STEP_USER_DATA_SCHEMA.schema.items():
            if str(key) == CONF_USERNAME:
                username_selector = selector
            elif str(key) == CONF_PASSWORD:
                password_selector = selector

        self.assertIsNotNone(username_selector)
        self.assertIsNotNone(password_selector)
        self.assertEqual(username_selector.config["type"], TextSelectorType.EMAIL)
        self.assertEqual(username_selector.config["autocomplete"], "username")
        self.assertEqual(password_selector.config["type"], TextSelectorType.PASSWORD)
        self.assertEqual(password_selector.config["autocomplete"], "current-password")

    def test_reauth_step_prefills_suggested_values(self) -> None:
        """Re-authentication flow form contains suggested values from existing config entry."""
        flow = ConfigFlow()
        flow.hass = MagicMock()

        mock_entry = MagicMock()
        mock_entry.data = {
            "username": "existing_user@example.com",
            "password": "old_password",
            "timeout": 10,
        }

        with patch.object(flow, "_get_reauth_entry", return_value=mock_entry):
            result = asyncio.run(flow.async_step_reauth(None))

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "reauth")

        schema = result["data_schema"]
        suggested_values = {
            k: k.description["suggested_value"]
            for k in schema.schema
            if isinstance(k.description, dict) and "suggested_value" in k.description
        }
        self.assertEqual(suggested_values.get("username"), "existing_user@example.com")
        self.assertEqual(suggested_values.get("timeout"), 10)


if __name__ == "__main__":
    unittest.main()
