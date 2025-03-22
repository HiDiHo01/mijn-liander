"""Constants for the Mijn Liander integration."""
from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

# Domain for the integration
DOMAIN = "mijn_liander"
COMPONENT_TITLE = "Mijn Liander"

UPDATE_INTERVAL = timedelta(minutes=360)
VERSION = "2024.9.14"
ATTRIBUTION: Final[str] = "Data provided by Liander"
MANUFACTURER: Final[str] = "Liander"

# Configuration keys
CONFIG_URL = "https://mijn-liander.web.liander.nl/"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Default values (not in use)
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""

# API Endpoints
API_VERSION = "v1"
API_LOGIN_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
    API_VERSION}/auth/login"
API_AANSLUITINGEN_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
    API_VERSION}/aansluitingen"
API_ME_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
    API_VERSION}/profielen/me"
API_AANVRAAGGEGEVENS_URL = f"https://mijn-liander-gateway.web.liander.nl/api/{
    API_VERSION}/aanvraaggegevens"

# Service names
SERVICE_NAME_ELEKTRA = "Elektra"
SERVICE_NAME_GAS = "Gas"
SERVICE_NAME_USER = "Gebruiker"

# Data keys
DATA_ACCOUNT: Final[str] = "Account"
"""Data key for account data."""

DATA_ELEKTRA: Final[str] = "Elektra"
"""Data key for elektra data."""

DATA_GAS: Final[str] = "Gas"
"""Data key for gas data."""

# Device and entity types
DEVICE_TYPE = "mijn_liander_device"
ENTITY_TYPE = "mijn_liander_entity"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
"""List of platforms supported by this integration."""
