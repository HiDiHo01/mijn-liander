"""Services for the Mijn Liander integration."""

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_GAS,
    SERVICE_NAME_USER,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_REMOVE_GROUP = "remove_group"
_GROUP_NAMES = {
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_USER,
    SERVICE_NAME_GAS,
}


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Mijn Liander services."""

    async def async_remove_group(call: ServiceCall) -> None:
        """Remove the selected Mijn Liander group and its owned entities."""
        device_id = call.data["device_id"]
        devices = dr.async_get(hass)
        entities = er.async_get(hass)
        device = devices.async_get(device_id)

        if device is None or device.model not in _GROUP_NAMES:
            raise HomeAssistantError(
                "Select an existing Elektra, Gebruiker, or Gas group "
                "from Mijn Liander."
            )

        matching_entries = [
            hass.config_entries.async_get_entry(entry_id)
            for entry_id in device.config_entries
        ]
        config_entries = [
            entry
            for entry in matching_entries
            if entry is not None
            and entry.domain == DOMAIN
            and _owns_group_device(device, entry.entry_id)
        ]
        if len(config_entries) != 1:
            raise HomeAssistantError(
                "The selected group is not uniquely owned by a Mijn Liander "
                "config entry; no registry entries were changed."
            )

        config_entry = config_entries[0]
        owned_entities = [
            entity
            for entity in er.async_entries_for_device(entities, device_id)
            if entity.platform == DOMAIN
            and entity.config_entry_id == config_entry.entry_id
        ]
        for entity in owned_entities:
            entities.async_remove(entity.entity_id)

        remaining_entities = er.async_entries_for_device(entities, device_id)
        if remaining_entities:
            _LOGGER.warning(
                "Kept Mijn Liander group device %s because it still has "
                "%d entity registry entries",
                device_id,
                len(remaining_entities),
            )
            return

        devices.async_update_device(
            device_id,
            remove_config_entry_id=config_entry.entry_id,
        )
        remaining_device = devices.async_get(device_id)
        if remaining_device is not None and not remaining_device.config_entries:
            devices.async_remove_device(device_id)

        _LOGGER.info(
            "Removed Mijn Liander %s group for config entry %s",
            device.model,
            config_entry.entry_id,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_GROUP,
        async_remove_group,
        schema=vol.Schema({vol.Required("device_id"): str}),
    )


def _owns_group_device(device: dr.DeviceEntry, entry_id: str) -> bool:
    """Validate the exact identifier used by a Mijn Liander group device."""
    expected_identifier = (
        entry_id
        if device.model == SERVICE_NAME_ELEKTRA
        else f"{entry_id}_{device.model}"
    )
    return (DOMAIN, expected_identifier) in device.identifiers
