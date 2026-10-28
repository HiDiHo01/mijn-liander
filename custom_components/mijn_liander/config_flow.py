# config_flow.py
import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import API_LOGIN_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
    ),
    vol.Required(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
    ),
    vol.Optional("timeout", default=5): vol.All(cv.positive_int, vol.Range(min=1, max=30))
})


async def _validate_input(username: str, password: str) -> dict[str, str]:
    """
    Validate the input by attempting to log in with the provided credentials.

    Args:
        username (str): The username for login.
        password (str): The password for login.

    Returns:
        dict: A dictionary with validation status and any errors.
    """
    login_data = {"username": username, "password": password}

    try:
        _LOGGER.debug("Sending login request to %s with data: %s",
                      API_LOGIN_URL, login_data)
        async with (
            aiohttp.ClientSession() as session,
            session.post(API_LOGIN_URL, json=login_data) as response,
        ):
            response.raise_for_status()
            login_response = await response.json()
            jwt_token = login_response.get("jwt")

            if jwt_token:
                _LOGGER.debug("Received JWT token: %s", jwt_token)
                return {"status": "success", "jwt_token": jwt_token}

            _LOGGER.warning("JWT token not found in response.")
            return {"status": "error", "error": "invalid_auth"}
    except aiohttp.ClientResponseError as e:
        return {"status": "error", "error": _map_http_error(e)}
    except (aiohttp.ClientError, TimeoutError):
        _LOGGER.exception("Network error validating credentials")
        return {"status": "error", "error": "cannot_connect"}


def _map_http_error(error: aiohttp.ClientResponseError) -> str:
    """
    Map HTTP error status to user-friendly error message codes.

    Args:
        error (aiohttp.ClientResponseError): The HTTP response error to map.

    Returns:
        str: A string representing the mapped error code.
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
            "Mapped HTTP error [%s] to error code '%s'", error.status, error_code)

    return error_code


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for the Liander integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step of user input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validated_data = STEP_USER_DATA_SCHEMA(user_input)
                username = validated_data[CONF_USERNAME]
                password = validated_data[CONF_PASSWORD]
                timeout = validated_data["timeout"]

                _LOGGER.debug("Validating user input: %s", user_input)

                try:
                    async with asyncio.timeout(timeout):
                        validation_result = await _validate_input(username, password)
                except TimeoutError:
                    _LOGGER.exception("Timeout error validating credentials")
                    validation_result = {"status": "error", "error": "cannot_connect"}

                if validation_result.get("status") == "success":
                    user_input["jwt_token"] = validation_result.get(
                        "jwt_token")

                    # Create the config entry
                    unique_id = username
                    _LOGGER.debug("Setting unique ID to '%s'", unique_id)
                    await self.async_set_unique_id(unique_id)
                    _LOGGER.debug(
                        "Checking if unique ID '%s' is already configured", unique_id)

                    # Check if the unique ID is already configured
                    if self._async_current_entries():
                        # Abort the flow with an error message if the unique ID is already configured
                        _LOGGER.debug(
                            "Unique ID '%s' is already configured", unique_id)
                        return self.async_abort(reason="already_configured")
                    # Create the configuration entry
                    result = self.async_create_entry(
                        title=username,
                        data=user_input
                    )
                    _LOGGER.debug(
                        "Successfully created config entry and devices")
                    return result
                else:
                    _LOGGER.error("Validation failed: %s", validation_result)
                    errors["base"] = validation_result.get(
                        "error", "unknown")

            except vol.Invalid:
                _LOGGER.exception("Schema validation failed")
                errors["base"] = "invalid_input"

            except Exception:
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle re-authentication if the credentials become invalid."""
        errors = {}

        entry = self._get_reauth_entry()

        if user_input:
            timeout = user_input.get("timeout", 5)
            try:
                async with asyncio.timeout(timeout):
                    validation_result = await _validate_input(
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                    )
            except TimeoutError:
                _LOGGER.exception("Timeout error validating credentials")
                validation_result = {"status": "error", "error": "cannot_connect"}

            if validation_result.get("status") == "success":
                self.hass.config_entries.async_update_entry(
                    entry, data=user_input
                )
                return self.async_abort(reason="reauth_successful")
            else:
                errors = {"base": validation_result.get(
                    "error", "unknown")}

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA,
            entry.data if entry else {}
        )

        return self.async_show_form(
            step_id="reauth",
            data_schema=data_schema,
            errors=errors
        )
