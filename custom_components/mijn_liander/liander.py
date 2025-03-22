# liander.py
import logging

import requests
from homeassistant.helpers.update_coordinator import UpdateFailed

from .coordinator import LianderDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MijnLiander:
    """Representation of the Mijn Liander component."""

    LOGIN_URL = "https://mijn-liander-gateway.web.liander.nl/api/v1/auth/login"

    def __init__(self, hass, username: str, password: str, coordinator: LianderDataUpdateCoordinator):
        """Initialize the component."""
        self.hass = hass
        self.username = username
        self.password = password
        self.coordinator = coordinator
        self.jwt_token = None

    async def authenticate(self) -> None:
        """Authenticate with the Mijn Liander API and store the JWT token."""
        try:
            _LOGGER.debug("Authenticating with Mijn Liander API...")

            login_data = {
                "username": self.username,
                "password": self.password
            }

            # Make the login request via coordinator
            response = await self.hass.async_add_executor_job(
                self.coordinator.perform_request,
                self.LOGIN_URL,
                "POST",
                None,
                login_data
            )

            response.raise_for_status()

            login_response = response.json()
            self.jwt_token = login_response.get("jwt")

            if not self.jwt_token:
                raise UpdateFailed("JWT token not found in login response.")

            _LOGGER.debug("Authentication successful, JWT token stored.")

        except requests.RequestException as e:
            _LOGGER.error("Error during Mijn Liander authentication: %s", e)
            raise UpdateFailed(f"Authentication failed: {e}") from e

    def get_coordinator(self):
        """Return the data update coordinator."""
        return self.coordinator

    async def close(self):
        """Close and clean up any resources."""
        _LOGGER.debug("Closing resources for Mijn Liander integration.")
        # Perform any cleanup actions, such as closing open sessions
