"""Migrate registry entries created by earlier Mijn Liander releases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry, entity_registry

from .const import DOMAIN, SERVICE_NAME_ELEKTRA

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _migrate_entity_unique_ids(
    registry: entity_registry.EntityRegistry,
    config_entry: ConfigEntry,
) -> None:
    """Keep the legacy entity IDs while using the current unique ID format."""
    legacy_prefix = f"{config_entry.unique_id}."
    for entry in list(
        registry.entities.get_entries_for_config_entry_id(config_entry.entry_id)
    ):
        if (
            entry.platform != DOMAIN
            or entry.domain not in {"sensor", "binary_sensor"}
            or not entry.unique_id.startswith(legacy_prefix)
        ):
            continue

        new_unique_id = (
            f"{config_entry.unique_id}_{entry.unique_id[len(legacy_prefix):]}"
        )
        existing_entity_id = registry.async_get_entity_id(
            entry.domain, entry.platform, new_unique_id
        )
        if existing_entity_id is not None:
            existing = registry.entities.get_entry(existing_entity_id)
            if existing is None or existing.config_entry_id != config_entry.entry_id:
                _LOGGER.error(
                    "Cannot migrate legacy Mijn Liander entity %s: "
                    "unique ID %s is already registered to another config entry",
                    entry.entity_id,
                    new_unique_id,
                )
                continue
            registry.async_remove(entry.entity_id)
            registry.async_update_entity(
                existing_entity_id,
                new_entity_id=entry.entity_id,
            )
            continue

        registry.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id
        )


def _migrate_electricity_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Merge the legacy electricity device into its current registry identity."""
    device_reg = device_registry.async_get(hass)
    entity_reg = entity_registry.async_get(hass)
    current_identifier = (DOMAIN, config_entry.entry_id)
    entry_devices = device_registry.async_entries_for_config_entry(
        device_reg, config_entry.entry_id
    )
    current_device = next(
        (
            device
            for device in entry_devices
            if current_identifier in device.identifiers
        ),
        None,
    )
    legacy_identifier_prefix = (DOMAIN, config_entry.entry_id)
    legacy_devices = [
        device
        for device in entry_devices
        if device.model == SERVICE_NAME_ELEKTRA
        and current_identifier not in device.identifiers
        and any(
            identifier[:2] == legacy_identifier_prefix
            and len(identifier) > 2
            for identifier in device.identifiers
        )
        and device.config_entries.issubset({config_entry.entry_id})
    ]

    if len(legacy_devices) != 1:
        if len(legacy_devices) > 1:
            _LOGGER.warning(
                "Found multiple legacy Mijn Liander electricity devices for "
                "config entry %s; leaving device registry unchanged",
                config_entry.entry_id,
            )
        return

    legacy_device = legacy_devices[0]
    if current_device is not None:
        if not current_device.config_entries.issubset(
            {config_entry.entry_id}
        ):
            _LOGGER.warning(
                "Cannot merge Mijn Liander electricity devices for config "
                "entry %s because the current device is associated with "
                "another config entry",
                config_entry.entry_id,
            )
            return

        current_entities = [
            entry
            for entry in entity_reg.entities.values()
            if entry.device_id == current_device.id
        ]
        if any(
            entry.config_entry_id != config_entry.entry_id
            or entry.platform != DOMAIN
            for entry in current_entities
        ):
            _LOGGER.warning(
                "Cannot merge Mijn Liander electricity devices for config "
                "entry %s because the current device has entities from another "
                "integration",
                config_entry.entry_id,
            )
            return

        for entry in current_entities:
            entity_reg.async_update_entity(
                entry.entity_id, device_id=legacy_device.id
            )
        device_reg.async_remove_device(current_device.id)

    device_reg.async_update_device(
        legacy_device.id,
        new_identifiers={current_identifier},
    )


async def async_migrate_registry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Migrate existing entity and device identities before platform setup."""
    _migrate_entity_unique_ids(entity_registry.async_get(hass), config_entry)
    _migrate_electricity_device(hass, config_entry)
