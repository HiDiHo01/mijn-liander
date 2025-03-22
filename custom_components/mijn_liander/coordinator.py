"""
This module defines the `LianderDataUpdateCoordinator` class for integrating with the Liander API 
to fetch and manage data updates related to energy usage, electrical connections, and more.

The `LianderDataUpdateCoordinator` is a custom implementation of the `DataUpdateCoordinator` 
from Home Assistant, designed to periodically fetch data from the Liander API. It handles authentication 
via JWT tokens, manages token renewal, and ensures the token remains valid before making requests to the API.

Key Features:
- **Token Management:** Automatically renews the authentication token when expired or nearing expiry.
- **Periodic Data Fetching:** Utilizes Home Assistant's `DataUpdateCoordinator` to fetch data at defined intervals.
- **Error Handling:** Implements robust error handling to manage issues such as expired tokens, network errors, 
  and invalid responses.
- **Integration with Liander API:** Fetches data from the Liander API, such as energy usage statistics and electrical connections.

Module Functionality:
- Initializes the coordinator with user credentials.
- Handles authentication requests and parses JWT tokens.
- Ensures the token is valid before each data fetch.
- Periodically requests data from the Liander API and processes the response.

By using this module, the integration keeps energy-related data up-to-date in Home Assistant while ensuring 
that authentication with the Liander API is securely managed.

Classes:
    LianderDataUpdateCoordinator: A custom coordinator that manages interaction with the Liander API 
    to periodically fetch data, handle token renewal, and manage errors.

Methods:
    _async_renew_token: Asynchronously renews the API token from the Liander API.
    get_valid_token: Ensures a valid JWT token is available, renewing if necessary.
    is_token_expired: Checks if the current token is expired or about to expire within a 5-minute buffer.
    _async_update_data: Fetches data from the Liander API using the valid token.
"""
# coordinator.py
import asyncio
import logging
import platform
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp
import async_timeout
import jwt
from aiohttp.client_exceptions import ContentTypeError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .const import (API_AANSLUITINGEN_URL, API_LOGIN_URL, CONF_PASSWORD,
                    CONF_USERNAME, DOMAIN, UPDATE_INTERVAL)

_LOGGER = logging.getLogger(__name__)


class LianderDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Liander API.

    This class handles the renewal of authentication tokens, checking if
    the token is expired, and fetching data from the Liander API. It uses 
    the home assistant DataUpdateCoordinator to periodically update the 
    fetched data.
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator with configuration and settings.

        Args:
            hass (HomeAssistant): Home Assistant instance.
            config_entry (ConfigEntry): Configuration entry for the integration.
        """
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self.hass = hass

        if platform.system() == 'Windows':
            # Set the event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        self._session = async_get_clientsession(hass)  # Gebruik HA's session
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_renew_token(self) -> None:
        """Renew the API token asynchronously.

        This method requests a new JWT token from the Liander API using the
        stored username and password. If the token is successfully renewed,
        it will decode the token to extract its expiration time.

        Raises:
            UpdateFailed: If the token renewal fails or an error occurs.
        """
        _LOGGER.debug("Renewing token...")

        login_data = {"username": self._username, "password": self._password}
        timeout = aiohttp.ClientTimeout(total=10)
        _LOGGER.debug("Request data: %s", login_data)

        try:
            async with async_timeout.timeout(10):
                async with self._session.post(API_LOGIN_URL, json=login_data, timeout=timeout) as response:
                    response.raise_for_status()
                    if response.status == 401:
                        _LOGGER.error("Token expired or unauthorized.")
                        raise UpdateFailed("Unauthorized, token expired.")
                    login_response = await response.json()

            self._token = login_response.get("jwt")
            if not self._token:
                raise UpdateFailed("JWT token not found in login response.")

            try:
                decoded_token = jwt.decode(self._token, options={"verify_signature": False})
                exp_timestamp = decoded_token.get("exp")
                self._token_expiry = (
                    datetime.fromtimestamp(exp_timestamp, timezone.utc)
                    if exp_timestamp
                    else datetime.now(timezone.utc) + timedelta(hours=1)
                )
            except jwt.DecodeError as e:
                _LOGGER.error("Failed to decode JWT token: %s", e)
                raise UpdateFailed(f"JWT decode error: {e}") from e

            _LOGGER.debug("Token refreshed successfully, new expiry at %s", self._token_expiry)

        except (ContentTypeError, KeyError) as e:
            _LOGGER.error("Invalid JSON response during token renewal: %s", e)
            raise UpdateFailed("Invalid JSON response during token renewal.")

        except aiohttp.ClientError as e:
            _LOGGER.error("Error renewing token: %s", e)
            raise UpdateFailed(f"Error renewing token: {e}") from e

        except Exception as e:
            _LOGGER.error("Unexpected error during token renewal: %s", e)
            raise UpdateFailed(f"Unexpected error renewing token: {e}") from e

    async def get_valid_token(self) -> str:
        """Ensure that we have a valid token.

        This method checks if a valid token is available. If not, it will 
        initiate token renewal. If the token is expired, it will renew the 
        token and return it.

        Returns:
            str: The valid JWT token.

        Raises:
            UpdateFailed: If the token is not available after renewal.
        """
        if not self._token:
            _LOGGER.debug("Token is not available, re-authenticating...")
            await self._async_renew_token()

        # Check if the token is expired
        if self.is_token_expired():
            _LOGGER.debug("Token is expired, re-authenticating...")
            await self._async_renew_token()

        if self._token is None:
            raise UpdateFailed("Token is not available after renewal.")
        return self._token

    def is_token_expired(self) -> bool:
        """Check if the current token is expired, with a 5-minute buffer.

        This method checks if the current token is expired or about to expire
        in less than 5 minutes. It includes a 5-minute buffer before expiration
        to ensure the token is refreshed before it becomes invalid.

        Returns:
            bool: True if the token is expired, otherwise False.
        """
        if not self._token_expiry:
            # Default to expired if no expiry time is set
            return True

        now = datetime.now(timezone.utc)  # Get the current time once for consistency

        # Warn if the token is about to expire in less than 30 minutes
        if self._token_expiry - timedelta(minutes=30) <= now:
            _LOGGER.warning("Token is about to expire in less than 30 minutes.")

        # Return True if the token is expired, with a 5-minute buffer
        return self._token_expiry - timedelta(minutes=5) <= now

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Liander API.

        This method fetches data from the Liander API using the current
        authentication token. If the token is valid and the request is 
        successful, it returns the fetched data.

        Returns:
            dict[str, Any]: The fetched data from the Liander API.

        Raises:
            UpdateFailed: If there is an error while fetching data.
        """
        jwt_token = await self.get_valid_token()
        headers = {"Authorization": f"Bearer {jwt_token}"}
        timeout = aiohttp.ClientTimeout(total=10)

        try:
            async with self._session.get(API_AANSLUITINGEN_URL, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                if response.status == 401:
                    _LOGGER.error("Token expired or unauthorized.")
                    raise UpdateFailed("Unauthorized, token expired.")
                if response.status == 503:
                    _LOGGER.error("Token expired or service unavailable.")
                    raise UpdateFailed("Service unavailable, token expired.")
                data = await response.json()

            _LOGGER.debug("Data fetched successfully from Liander API: %s", data)
            return data

        except ContentTypeError:
            _LOGGER.error("Invalid JSON response received from Liander API.")
            raise UpdateFailed("Invalid JSON response from Liander API.")

        except aiohttp.ClientError as e:
            _LOGGER.error("Error fetching data from Liander API: %s", e)
            raise UpdateFailed(f"Error fetching data from Liander API: {e}") from e

        except Exception as e:
            _LOGGER.error("Unexpected error fetching data: %s", e)
            raise UpdateFailed(f"Unexpected error fetching data: {e}") from e


# Example usage:
example_data: list[dict[str, Any]] = [
    {
        "adres": {
            "postcode": "1000 AAB",
            "straat": "Mijnstraat",
            "huisnummer": "1",
            "toevoeging": "",
            "plaats": "AMSTERDAM"
        },
        "aansluitingen": {
            "elektra": [
                {
                    "type": "ElektraAansluiting",
                    "ean": "123456789012345678",
                    "aansluitwaarde": "3x25A",
                    "status": "In bedrijf",
                    "netwerkkosten": "400.92",
                    "meters": [
                        {
                            "type": "Elektrameter",
                            "meternummer": "E0000000000000000",
                            "aantalTelwerken": 4,
                            "aantalFasen": "3"
                        }
                    ],
                    "maximaalVermogen": "17"
                }
            ],
            "gas": []
        }
    }
]
