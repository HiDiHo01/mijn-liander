"""Tests for migrating Mijn Liander entity and device registry entries."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.mijn_liander.const import DOMAIN
from custom_components.mijn_liander.migration import (
    _migrate_electricity_device,
    _migrate_sensor_unique_ids,
)


@dataclass
class FakeEntity:
    """Entity registry entry used by migration tests."""

    entity_id: str
    unique_id: str
    domain: str
    platform: str
    config_entry_id: str
    device_id: str | None = None


class FakeEntityCollection(dict[str, FakeEntity]):
    """Small subset of the entity registry collection API."""

    def get_entries_for_config_entry_id(
        self, config_entry_id: str
    ) -> list[FakeEntity]:
        return [
            entry
            for entry in self.values()
            if entry.config_entry_id == config_entry_id
        ]

    def get_entry(self, entity_id: str) -> FakeEntity | None:
        return self.get(entity_id)


class FakeEntityRegistry:
    """Small subset of the entity registry API."""

    def __init__(self, *entries: FakeEntity) -> None:
        self.entities = FakeEntityCollection(
            (entry.entity_id, entry) for entry in entries
        )

    def async_get_entity_id(
        self, domain: str, platform: str, unique_id: str
    ) -> str | None:
        return next(
            (
                entry.entity_id
                for entry in self.entities.values()
                if entry.domain == domain
                and entry.platform == platform
                and entry.unique_id == unique_id
            ),
            None,
        )

    def async_remove(self, entity_id: str) -> None:
        self.entities.pop(entity_id)

    def async_update_entity(self, entity_id: str, **changes: object) -> None:
        entry = self.entities[entity_id]
        for key, value in changes.items():
            if key == "new_entity_id":
                self.entities.pop(entity_id)
                entry.entity_id = value
                self.entities[value] = entry
            else:
                attribute = "unique_id" if key == "new_unique_id" else key
                setattr(entry, attribute, value)


@dataclass
class FakeDevice:
    """Device registry entry used by migration tests."""

    id: str
    identifiers: set[tuple[object, ...]]
    model: str
    config_entries: set[str]


class FakeDeviceRegistry:
    """Small subset of the device registry API."""

    def __init__(self, *devices: FakeDevice) -> None:
        self.devices = {device.id: device for device in devices}

    def async_get_device(
        self, *, identifiers: set[tuple[str, str]]
    ) -> FakeDevice | None:
        return next(
            (
                device
                for device in self.devices.values()
                if identifiers.issubset(device.identifiers)
            ),
            None,
        )

    def async_remove_device(self, device_id: str) -> None:
        self.devices.pop(device_id)

    def async_update_device(
        self, device_id: str, *, new_identifiers: set[tuple[str, str]]
    ) -> FakeDevice:
        device = self.devices[device_id]
        device.identifiers = set(new_identifiers)
        return device


class RegistryMigrationTests(unittest.TestCase):
    """Verify legacy registry identities migrate without losing entity IDs."""

    def setUp(self) -> None:
        self.config_entry = SimpleNamespace(
            entry_id="entry-id",
            unique_id="account@example.com",
        )

    def test_migrate_legacy_sensor_unique_id(self) -> None:
        """Legacy sensor IDs are preserved when their unique ID changes."""
        legacy = FakeEntity(
            entity_id="sensor.liander_address",
            unique_id="account@example.com.address",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(legacy)

        _migrate_sensor_unique_ids(registry, self.config_entry)
        _migrate_sensor_unique_ids(registry, self.config_entry)

        self.assertEqual(
            registry.entities["sensor.liander_address"].unique_id,
            "account@example.com_address",
        )

    def test_migrate_sensor_when_updated_duplicate_exists(self) -> None:
        """Keep the legacy entity ID and replace its duplicate registry entry."""
        legacy = FakeEntity(
            entity_id="sensor.liander_address",
            unique_id="account@example.com.address",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        updated = FakeEntity(
            entity_id="sensor.liander_address_2",
            unique_id="account@example.com_address",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(legacy, updated)

        _migrate_sensor_unique_ids(registry, self.config_entry)
        _migrate_sensor_unique_ids(registry, self.config_entry)

        self.assertEqual(
            list(registry.entities),
            ["sensor.liander_address"],
        )
        self.assertEqual(
            registry.entities["sensor.liander_address"].unique_id,
            "account@example.com_address",
        )
        self.assertEqual(
            registry.entities["sensor.liander_address"].entity_id,
            "sensor.liander_address",
        )

    def test_merge_duplicate_electricity_devices(self) -> None:
        """Move current entities onto the legacy device and retain its ID."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
        )
        current_device = FakeDevice(
            id="current-device",
            identifiers={(DOMAIN, "entry-id")},
            model="Elektra",
            config_entries={"entry-id"},
        )
        entity = FakeEntity(
            entity_id="sensor.liander_new_value",
            unique_id="account@example.com_new_value",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
            device_id="current-device",
        )
        devices = FakeDeviceRegistry(legacy_device, current_device)
        entities = FakeEntityRegistry(entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(SimpleNamespace(), self.config_entry)
            _migrate_electricity_device(SimpleNamespace(), self.config_entry)

        self.assertEqual(set(devices.devices), {"legacy-device"})
        self.assertEqual(
            legacy_device.identifiers,
            {(DOMAIN, "entry-id")},
        )
        self.assertEqual(entity.device_id, "legacy-device")

    def test_do_not_merge_device_with_foreign_entities(self) -> None:
        """Leave device registry untouched if the duplicate has unrelated entities."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
        )
        current_device = FakeDevice(
            id="current-device",
            identifiers={(DOMAIN, "entry-id")},
            model="Elektra",
            config_entries={"entry-id"},
        )
        foreign_entity = FakeEntity(
            entity_id="sensor.other_integration",
            unique_id="other",
            domain="sensor",
            platform="other_integration",
            config_entry_id="other-entry",
            device_id="current-device",
        )
        devices = FakeDeviceRegistry(legacy_device, current_device)
        entities = FakeEntityRegistry(foreign_entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(SimpleNamespace(), self.config_entry)

        self.assertEqual(
            set(devices.devices),
            {"legacy-device", "current-device"},
        )
        self.assertEqual(
            legacy_device.identifiers,
            {(DOMAIN, "entry-id", None)},
        )
        self.assertEqual(foreign_entity.device_id, "current-device")


if __name__ == "__main__":
    unittest.main()
