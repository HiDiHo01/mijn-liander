"""Migrate registry entries created by earlier Mijn Liander releases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry, entity_registry

from .const import DOMAIN, SERVICE_NAME_ELEKTRA, SERVICE_NAME_GAS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)

LEGACY_BINARY_SENSOR_KEYS = {
    "contract": "contract_active",
    "toestemmingVoorUitlezen": "permission_to_read_data",
    "slimmeMeter": "smart_meter",
    "geschiktVoorTerugleveren": "suitable_for_backfeeding",
    "geschiktVoorDubbeltarief": "suitable_for_dual_tariff",
    "levertTerug": "backfeeding_energy",
}


def _process_single_entity_migration(
    registry: entity_registry.EntityRegistry,
    config_entry: ConfigEntry,
    entry: entity_registry.RegistryEntry,
    account_id: str,
    dotted_prefix: str,
    underscored_prefix: str,
    obsolete_sensor_unique_ids: set[str],
) -> bool:
    """Migrate a single entity registry entry, returning True if migrated/removed."""
    if entry.platform != DOMAIN:
        return False

    if entry.domain == "binary_sensor" and entry.unique_id in {
        f"{dotted_prefix}analog",
        f"{underscored_prefix}analog",
    }:
        registry.async_remove(entry.entity_id)
        return True

    if entry.domain == "sensor" and entry.unique_id in obsolete_sensor_unique_ids:
        registry.async_remove(entry.entity_id)
        return True

    if entry.domain not in {"sensor", "binary_sensor"}:
        return False

    if entry.unique_id.startswith(dotted_prefix):
        legacy_key = entry.unique_id[len(dotted_prefix) :]
    elif entry.domain == "binary_sensor" and entry.unique_id.startswith(
        underscored_prefix
    ):
        legacy_key = entry.unique_id[len(underscored_prefix) :]
        if legacy_key not in LEGACY_BINARY_SENSOR_KEYS:
            return False
    else:
        return False

    current_key = (
        LEGACY_BINARY_SENSOR_KEYS.get(legacy_key, legacy_key)
        if entry.domain == "binary_sensor"
        else legacy_key
    )
    new_unique_id = f"{account_id}_{current_key}"
    return _migrate_entity_preserving_id(registry, config_entry, entry, new_unique_id)


def _migrate_entity_preserving_id(
    registry: entity_registry.EntityRegistry,
    config_entry: ConfigEntry,
    entry: entity_registry.RegistryEntry,
    new_unique_id: str,
) -> bool:
    """Retain an owned current entry, or update the legacy unique ID in place."""
    existing_entity_id = registry.async_get_entity_id(
        entry.domain,
        entry.platform,
        new_unique_id,
    )

    if existing_entity_id is not None:
        existing = registry.async_get(existing_entity_id)
        if existing is None or existing.config_entry_id != config_entry.entry_id:
            _LOGGER.error(
                "Cannot migrate legacy Mijn Liander entity %s: "
                "unique ID %s is already registered to another config entry",
                entry.entity_id,
                new_unique_id,
            )
            return False

        registry.async_remove(entry.entity_id)
        return True

    registry.async_update_entity(
        entry.entity_id,
        new_unique_id=new_unique_id,
    )
    return True


def _migrate_entity_unique_ids(
    registry: entity_registry.EntityRegistry,
    config_entry: ConfigEntry,
) -> None:
    """Use current unique IDs, retaining current entries when duplicates exist."""
    account_id = config_entry.unique_id
    dotted_prefix = f"{account_id}."
    underscored_prefix = f"{account_id}_"
    obsolete_sensor_unique_ids = {
        f"{dotted_prefix}status",
        f"{underscored_prefix}status",
    }
    migrated_count = 0

    for entry in registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    ):
        if _process_single_entity_migration(
            registry,
            config_entry,
            entry,
            account_id,
            dotted_prefix,
            underscored_prefix,
            obsolete_sensor_unique_ids,
        ):
            migrated_count += 1

    if migrated_count:
        _LOGGER.info(
            "Migrated or removed %s legacy Mijn Liander entity registry entries",
            migrated_count,
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
        device_reg,
        config_entry.entry_id,
    )

    current_device = next(
        (
            device
            for device in entry_devices
            if current_identifier in device.identifiers
        ),
        None,
    )

    legacy_identifier_prefix = current_identifier
    legacy_devices = [
        device
        for device in entry_devices
        if (
            device.model == SERVICE_NAME_ELEKTRA
            and current_identifier not in device.identifiers
            and any(
                identifier[:2] == legacy_identifier_prefix and len(identifier) > 2
                for identifier in device.identifiers
            )
            and device.config_entry_id == config_entry.entry_id
        )
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
        if current_device.config_entry_id != config_entry.entry_id:
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
            entry.config_entry_id != config_entry.entry_id or entry.platform != DOMAIN
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
                entry.entity_id,
                device_id=legacy_device.id,
            )

        device_reg.async_remove_device(current_device.id)

    device_reg.async_update_device(
        legacy_device.id,
        new_identifiers={current_identifier},
    )


def _is_owned_gas_entity(
    entry: entity_registry.RegistryEntry,
    config_entry: ConfigEntry,
    gas_device_id: str | None,
    gas_prefixes: tuple[str, ...],
) -> bool:
    """Recognize owned gas entries by their device or established unique-ID prefix."""
    if entry.platform != DOMAIN or entry.config_entry_id != config_entry.entry_id:
        return False
    return (
        gas_device_id is not None and entry.device_id == gas_device_id
    ) or entry.unique_id.startswith(gas_prefixes)


def _remove_empty_owned_gas_device(
    device_reg: device_registry.DeviceRegistry,
    entity_reg: entity_registry.EntityRegistry,
    gas_device: device_registry.DeviceEntry | None,
    config_entry: ConfigEntry,
) -> None:
    """Remove only an owned gas device with no remaining entities from any entry."""
    if gas_device is None or gas_device.config_entry_id != config_entry.entry_id:
        return
    if gas_device.config_entries != {config_entry.entry_id}:
        return
    if any(entry.device_id == gas_device.id for entry in entity_reg.entities.values()):
        return
    device_reg.async_remove_device(gas_device.id)


def remove_inactive_gas_registry_entries(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Remove gas entity and device records when no gas contract is active."""
    device_reg = device_registry.async_get(hass)
    entity_reg = entity_registry.async_get(hass)
    gas_identifier = (DOMAIN, f"{config_entry.entry_id}_{SERVICE_NAME_GAS}")

    gas_devices = [
        device
        for device in device_registry.async_entries_for_config_entry(
            device_reg,
            config_entry.entry_id,
        )
        if (gas_identifier in device.identifiers and device.model == SERVICE_NAME_GAS)
    ]

    if len(gas_devices) > 1:
        _LOGGER.warning(
            "Found multiple Mijn Liander gas devices for config entry %s; "
            "leaving gas registry entries unchanged",
            config_entry.entry_id,
        )
        return

    gas_device = gas_devices[0] if gas_devices else None
    gas_device_id = gas_device.id if gas_device is not None else None
    gas_prefixes = (
        (f"{config_entry.unique_id}.gas_", f"{config_entry.unique_id}_gas_")
        if config_entry.unique_id is not None
        else ()
    )

    gas_entities = [
        entry
        for entry in entity_reg.entities.values()
        if _is_owned_gas_entity(entry, config_entry, gas_device_id, gas_prefixes)
    ]

    for entry in gas_entities:
        entity_reg.async_remove(entry.entity_id)

    removed_entities = len(gas_entities)

    _remove_empty_owned_gas_device(device_reg, entity_reg, gas_device, config_entry)

    if removed_entities:
        _LOGGER.info(
            "Removed %s Mijn Liander gas entity registry entries because "
            "no active gas contract is present",
            removed_entities,
        )


async def async_migrate_registry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Migrate existing entity and device identities before platform setup."""
    _migrate_entity_unique_ids(
        entity_registry.async_get(hass),
        config_entry,
    )
    _migrate_electricity_device(
        hass,
        config_entry,
    )
