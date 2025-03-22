# config_flow.py
import logging
from typing import Any, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional("timeout", default=5): vol.All(cv.positive_int, vol.Range(min=1, max=30))
})


async def _validate_input(username: str, password: str, timeout: int) -> dict[str, str]:
    """
    Validate the input by attempting to log in with the provided credentials.

    Args:
        username (str): The username for login.
        password (str): The password for login.
        timeout (int): The timeout value for the request.

    Returns:
        dict: A dictionary with validation status and any errors.
    """
    LOGIN_URL = "https://mijn-liander-gateway.web.liander.nl/api/v1/auth/login"
    login_data = {"username": username, "password": password}

    try:
        _LOGGER.debug("Sending login request to %s with data: %s",
                      LOGIN_URL, login_data)
        async with aiohttp.ClientSession() as session:
            async with session.post(LOGIN_URL, json=login_data, timeout=timeout) as response:
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
    except aiohttp.ClientError as e:
        _LOGGER.error("Network error validating credentials: %s", e)
        return {"status": "error", "error": "network_error"}


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

    error_code = status_error_mapping.get(error.status, "unknown_error")

    if error_code == "unknown_error":
        _LOGGER.error("Unhandled HTTP error [%s]: %s", error.status, error)
    else:
        _LOGGER.debug(
            "Mapped HTTP error [%s] to error code '%s'", error.status, error_code)

    return error_code


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for the Liander integration."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step of user input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validated_data = STEP_USER_DATA_SCHEMA(user_input)
                username = validated_data[CONF_USERNAME]
                password = validated_data[CONF_PASSWORD]
                timeout = validated_data["timeout"]

                _LOGGER.debug("Validating user input: %s", user_input)

                validation_result = await _validate_input(username, password, timeout)

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
                    error_code = validation_result.get(
                        "error", "unknown_error")
                    errors["base"] = self.map_error_to_message(error_code)

            except vol.Invalid as e:
                _LOGGER.error("Schema validation failed: %s", e)
                errors["base"] = "invalid_input"

            except Exception as e:
                _LOGGER.error("Unexpected exception during validation: %s", e)
                errors["base"] = f"unknown_error: {e}"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    @staticmethod
    def map_error_to_message(error_code: str) -> str:
        """Map error code to user-friendly error message."""
        error_mapping = {
            "invalid_auth": "Invalid username or password.",
            "service_unavailable": "The service is currently unavailable. Please try again later.",
            "network_error": "Network error. Check your internet connection.",
            "invalid_timeout": "The timeout value is invalid. Please provide a value between 1 and 30 seconds.",
            "already_configured": "This entry is already configured. Please use a different username or update the existing configuration.",
            "unknown_error": "An unknown error occurred. Please try again."
        }
        return error_mapping.get(error_code, "unknown_error")

    async def async_step_reauth(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Handle re-authentication if the credentials become invalid."""
        errors = {}

        if user_input:
            validation_result = await _validate_input(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input.get("timeout", 5)
            )

            if validation_result.get("status") == "success":
                self.hass.config_entries.async_update_entry(
                    self.context["entry_id"], data=user_input
                )
                return self.async_abort(reason="reauth_successful")
            else:
                errors = {"base": validation_result.get(
                    "error", "unknown_error")}

        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )
