"""Configure isolated Mijn Liander accounts and renew their credentials."""

import asyncio
import logging
from typing import TypedDict

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import API_LOGIN_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): vol.All(cv.string, vol.Strip, vol.Email()),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional("timeout", default=5): vol.All(
            cv.positive_int, vol.Range(min=1, max=30)
        ),
    }
)


class _LoginData(TypedDict):
    """Describe credentials after the input schema has validated their types."""

    username: str
    password: str
    timeout: int


def _normalize_email(email_address: str) -> str:
    """Return a case-insensitive account identity without surrounding whitespace."""
    return email_address.strip().casefold()


async def _validate_input(username: str, password: str) -> dict[str, str]:
    """Validate the input by logging in with the provided credentials.

    Args:
        username: The username for login.
        password: The password for login.

    Returns:
        A dictionary with validation status and any errors.
    """
    login_data = {"username": username, "password": password}

    try:
        _LOGGER.debug("Sending login request to Mijn Liander")
        async with (
            aiohttp.ClientSession() as session,
            session.post(API_LOGIN_URL, json=login_data) as response,
        ):
            response.raise_for_status()
            login_response: object = await response.json()
            jwt_token = (
                login_response.get("jwt") if isinstance(login_response, dict) else None
            )

            if isinstance(jwt_token, str) and jwt_token.strip():
                _LOGGER.debug("Mijn Liander authentication succeeded")
                return {"status": "success", "jwt_token": jwt_token}

            _LOGGER.warning("Valid JWT token not found in login response")
            return {"status": "error", "error": "invalid_auth"}
    except aiohttp.ClientResponseError as error:
        return {"status": "error", "error": _map_http_error(error)}
    except aiohttp.ClientError, TimeoutError:
        _LOGGER.exception("Network error validating credentials")
        return {"status": "error", "error": "cannot_connect"}


def _map_http_error(error: aiohttp.ClientResponseError) -> str:
    """Map HTTP error status to user-friendly error message codes.

    Args:
        error: The HTTP response error to map.

    Returns:
        A string representing the mapped error code.
    """
    status_error_mapping = {
        401: "invalid_auth",
        403: "forbidden",
        404: "not_found",
        429: "too_many_requests",
        503: "service_unavailable",
    }

    error_code = status_error_mapping.get(error.status, "unknown")

    if error_code == "unknown":
        _LOGGER.error("Unhandled HTTP error [%s]", error.status)
    else:
        _LOGGER.debug(
            "Mapped HTTP error [%s] to error code '%s'", error.status, error_code
        )

    return error_code


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle configuration and reauthentication for each Mijn Liander account."""

    VERSION = 1

    async def _async_check_account(self, username: str) -> None:
        """Reject duplicate accounts, including entries with legacy unique IDs."""
        account_id = _normalize_email(username)
        await self.async_set_unique_id(account_id)
        self._abort_if_unique_id_configured()

        if any(
            isinstance(identity, str) and _normalize_email(identity) == account_id
            for entry in self._async_current_entries()
            for identity in (entry.unique_id, entry.data.get(CONF_USERNAME))
        ):
            raise AbortFlow("already_configured")

    async def _async_validate_credentials(
        self, credentials: _LoginData
    ) -> dict[str, str]:
        """Authenticate within the configured timeout and map unexpected errors."""
        try:
            async with asyncio.timeout(credentials["timeout"]):
                return await _validate_input(
                    credentials[CONF_USERNAME], credentials[CONF_PASSWORD]
                )
        except TimeoutError:
            _LOGGER.exception("Timeout error validating credentials")
            return {"status": "error", "error": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception during validation")
            return {"status": "error", "error": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure each email address once while allowing other accounts."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validated_data: _LoginData = STEP_USER_DATA_SCHEMA(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_input"
            else:
                username = validated_data[CONF_USERNAME]
                await self._async_check_account(username)
                validation_result = await self._async_validate_credentials(
                    validated_data
                )

                if validation_result["status"] == "success":
                    return self.async_create_entry(
                        title=username,
                        data={
                            **validated_data,
                            "jwt_token": validation_result["jwt_token"],
                        },
                    )

                errors["base"] = validation_result.get("error", "unknown")

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initialize reauthentication without treating stored data as form input."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, object] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Renew credentials for the same account, preserving existing identities."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                validated_data: _LoginData = STEP_USER_DATA_SCHEMA(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_input"
            else:
                stored_username = entry.data.get(CONF_USERNAME, entry.unique_id)
                if not isinstance(stored_username, str) or _normalize_email(
                    validated_data[CONF_USERNAME]
                ) != _normalize_email(stored_username):
                    errors["base"] = "wrong_account"
                else:
                    validation_result = await self._async_validate_credentials(
                        validated_data
                    )
                    if validation_result["status"] == "success":
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates={
                                **validated_data,
                                "jwt_token": validation_result["jwt_token"],
                            },
                        )
                    errors["base"] = validation_result.get("error", "unknown")

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, entry.data
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
        )
