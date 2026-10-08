"""Tests for migrating Mijn Liander entity and device registry entries."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.mijn_liander.const import DOMAIN
from custom_components.mijn_liander.migration import (
    _migrate_electricity_device,
    _migrate_entity_unique_ids,
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
        self,
        config_entry_id: str,
    ) -> list[FakeEntity]:
        """Return entities belonging to a config entry."""
        return [
            entry
            for entry in self.values()
            if entry.config_entry_id == config_entry_id
        ]

    def get_entry(self, entity_id: str) -> FakeEntity | None:
        """Return an entity by entity ID."""
        return self.get(entity_id)


class FakeEntityRegistry:
    """Small subset of the entity registry API."""

    def __init__(self, *entries: FakeEntity) -> None:
        """Initialize the fake entity registry."""
        self.entities = FakeEntityCollection(
            (entry.entity_id, entry) for entry in entries
        )

    def async_get_entity_id(
        self,
        domain: str,
        platform: str,
        unique_id: str,
    ) -> str | None:
        """Return the entity ID matching domain, platform, and unique ID."""
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
        """Remove an entity from the fake registry."""
        self.entities.pop(entity_id)

    def async_update_entity(
        self,
        entity_id: str,
        **changes: object,
    ) -> None:
        """Update an entity in the fake registry."""
        entry = self.entities[entity_id]

        for key, value in changes.items():
            if key == "new_entity_id":
                if not isinstance(value, str):
                    raise TypeError("new_entity_id must be a string")

                self.entities.pop(entity_id)
                entry.entity_id = value
                self.entities[value] = entry
                continue

            attribute = "unique_id" if key == "new_unique_id" else key
            setattr(entry, attribute, value)


@dataclass
class FakeDevice:
    """Device registry entry used by migration tests."""

    id: str
    identifiers: set[tuple[object, ...]]
    model: str
    config_entries: set[str]
    config_entry_id: str


class FakeDeviceRegistry:
    """Small subset of the device registry API."""

    def __init__(self, *devices: FakeDevice) -> None:
        """Initialize the fake device registry."""
        self.devices = {device.id: device for device in devices}

    def async_remove_device(self, device_id: str) -> None:
        """Remove a device from the fake registry."""
        self.devices.pop(device_id)

    def async_update_device(
        self,
        device_id: str,
        *,
        new_identifiers: set[tuple[object, ...]],
    ) -> FakeDevice:
        """Update device identifiers in the fake registry."""
        device = self.devices[device_id]
        device.identifiers = new_identifiers
        return device


class RegistryMigrationTests:
    """Verify legacy registry identities migrate safely and idempotently."""

    def setup_method(self) -> None:
        """Create a fake config entry used by each test."""
        self.config_entry = SimpleNamespace(
            entry_id="entry-id",
            unique_id="account@example.com",
        )

    def test_migrate_legacy_sensor_unique_id(self) -> None:
        """Preserve the legacy sensor entity ID while updating its unique ID."""
        legacy = FakeEntity(
            entity_id="sensor.liander_address",
            unique_id="account@example.com.address",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(legacy)

        _migrate_entity_unique_ids(registry, self.config_entry)
        _migrate_entity_unique_ids(registry, self.config_entry)

        assert (
            registry.entities["sensor.liander_address"].unique_id
            == "account@example.com_address"
        )

    def test_migrate_sensor_when_updated_duplicate_exists(self) -> None:
        """Keep the legacy entity ID when the current unique ID already exists."""
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

        _migrate_entity_unique_ids(registry, self.config_entry)
        _migrate_entity_unique_ids(registry, self.config_entry)

        assert list(registry.entities) == ["sensor.liander_address"]
        assert (
            registry.entities["sensor.liander_address"].unique_id
            == "account@example.com_address"
        )
        assert (
            registry.entities["sensor.liander_address"].entity_id
            == "sensor.liander_address"
        )

    def test_migrate_legacy_binary_sensor_unique_id(self) -> None:
        """Migrate a legacy binary-sensor ID using the shared ID format."""
        legacy = FakeEntity(
            entity_id="binary_sensor.liander_status",
            unique_id="account@example.com.status",
            domain="binary_sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(legacy)

        _migrate_entity_unique_ids(registry, self.config_entry)

        assert (
            registry.entities["binary_sensor.liander_status"].unique_id
            == "account@example.com_status"
        )

    def test_migrate_renamed_legacy_binary_sensor_keys(self) -> None:
        """Migrate legacy binary-sensor keys to their current unique IDs."""
        key_mappings = {
            "contract": "contract_active",
            "toestemmingVoorUitlezen": "permission_to_read_data",
            "slimmeMeter": "smart_meter",
            "geschiktVoorTerugleveren": "suitable_for_backfeeding",
            "geschiktVoorDubbeltarief": "suitable_for_dual_tariff",
            "levertTerug": "backfeeding_energy",
        }

        legacy_entities = [
            FakeEntity(
                entity_id=f"binary_sensor.liander_{legacy_key}",
                unique_id=f"account@example.com_{legacy_key}",
                domain="binary_sensor",
                platform=DOMAIN,
                config_entry_id=self.config_entry.entry_id,
            )
            for legacy_key in key_mappings
        ]

        duplicate = FakeEntity(
            entity_id="binary_sensor.liander_contract_active_new",
            unique_id="account@example.com_contract_active",
            domain="binary_sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )

        registry = FakeEntityRegistry(*legacy_entities, duplicate)

        _migrate_entity_unique_ids(registry, self.config_entry)
        _migrate_entity_unique_ids(registry, self.config_entry)

        assert set(registry.entities) == {
            f"binary_sensor.liander_{legacy_key}"
            for legacy_key in key_mappings
        }

        for legacy_key, current_key in key_mappings.items():
            entity = registry.entities[f"binary_sensor.liander_{legacy_key}"]
            assert entity.unique_id == f"account@example.com_{current_key}"

    def test_remove_obsolete_legacy_status_sensor(self) -> None:
        """Remove the obsolete sensor status entity and its migrated duplicate."""
        legacy_status = FakeEntity(
            entity_id="sensor.liander_status",
            unique_id="account@example.com.status",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        previously_migrated_status = FakeEntity(
            entity_id="sensor.liander_status_2",
            unique_id="account@example.com_status",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(
            legacy_status,
            previously_migrated_status,
        )

        _migrate_entity_unique_ids(registry, self.config_entry)

        assert registry.entities == {}

    def test_do_not_migrate_unrelated_platform_entity(self) -> None:
        """Leave entities from another integration untouched."""
        entity = FakeEntity(
            entity_id="sensor.other_integration",
            unique_id="account@example.com.address",
            domain="sensor",
            platform="other_integration",
            config_entry_id=self.config_entry.entry_id,
        )
        registry = FakeEntityRegistry(entity)

        _migrate_entity_unique_ids(registry, self.config_entry)

        assert registry.entities["sensor.other_integration"].unique_id == (
            "account@example.com.address"
        )

    def test_do_not_migrate_entity_from_another_config_entry(self) -> None:
        """Leave an entity from another config entry untouched."""
        entity = FakeEntity(
            entity_id="sensor.liander_other",
            unique_id="account@example.com.address",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id="other-entry",
        )
        registry = FakeEntityRegistry(entity)

        _migrate_entity_unique_ids(registry, self.config_entry)

        assert registry.entities["sensor.liander_other"].unique_id == (
            "account@example.com.address"
        )

    def test_merge_duplicate_electricity_devices(self) -> None:
        """Move current entities to the legacy device and retain its ID."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        current_device = FakeDevice(
            id="current-device",
            identifiers={(DOMAIN, "entry-id")},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        entity = FakeEntity(
            entity_id="sensor.liander_new_value",
            unique_id="account@example.com_new_value",
            domain="sensor",
            platform=DOMAIN,
            config_entry_id=self.config_entry.entry_id,
            device_id="current-device",
        )
        devices = FakeDeviceRegistry(
            legacy_device,
            current_device,
        )
        entities = FakeEntityRegistry(entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=list(devices.devices.values()),
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )

        assert set(devices.devices) == {"legacy-device"}
        assert legacy_device.identifiers == {(DOMAIN, "entry-id")}
        assert entity.device_id == "legacy-device"

    def test_migrate_legacy_electricity_device_identity(self) -> None:
        """Update a legacy device identity when no duplicate exists."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        devices = FakeDeviceRegistry(legacy_device)
        entities = FakeEntityRegistry()

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=list(devices.devices.values()),
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )

        assert set(devices.devices) == {"legacy-device"}
        assert legacy_device.identifiers == {(DOMAIN, "entry-id")}

    def test_do_not_merge_device_with_foreign_entities(self) -> None:
        """Leave a duplicate device with foreign entities untouched."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        current_device = FakeDevice(
            id="current-device",
            identifiers={(DOMAIN, "entry-id")},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        foreign_entity = FakeEntity(
            entity_id="sensor.other_integration",
            unique_id="other",
            domain="sensor",
            platform="other_integration",
            config_entry_id="other-entry",
            device_id="current-device",
        )
        devices = FakeDeviceRegistry(
            legacy_device,
            current_device,
        )
        entities = FakeEntityRegistry(foreign_entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=list(devices.devices.values()),
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )

        assert set(devices.devices) == {
            "legacy-device",
            "current-device",
        }
        assert legacy_device.identifiers == {
            (DOMAIN, "entry-id", None)
        }
        assert foreign_entity.device_id == "current-device"

    def test_do_not_merge_device_associated_with_another_config_entry(
        self,
    ) -> None:
        """Keep a duplicate device owned by another config entry."""
        legacy_device = FakeDevice(
            id="legacy-device",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        current_device = FakeDevice(
            id="current-device",
            identifiers={(DOMAIN, "entry-id")},
            model="Elektra",
            config_entries={"entry-id", "other-entry"},
            config_entry_id="other-entry",
        )
        devices = FakeDeviceRegistry(
            legacy_device,
            current_device,
        )
        entities = FakeEntityRegistry()

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=list(devices.devices.values()),
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )

        assert set(devices.devices) == {
            "legacy-device",
            "current-device",
        }
        assert legacy_device.identifiers == {
            (DOMAIN, "entry-id", None)
        }
        assert current_device.identifiers == {(DOMAIN, "entry-id")}
        assert current_device.config_entries == {
            "entry-id",
            "other-entry",
        }

    def test_do_not_merge_multiple_legacy_devices(self) -> None:
        """Leave the registry unchanged when multiple legacy devices exist."""
        legacy_device_one = FakeDevice(
            id="legacy-device-1",
            identifiers={(DOMAIN, "entry-id", None)},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        legacy_device_two = FakeDevice(
            id="legacy-device-2",
            identifiers={(DOMAIN, "entry-id", "legacy")},
            model="Elektra",
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        devices = FakeDeviceRegistry(
            legacy_device_one,
            legacy_device_two,
        )
        entities = FakeEntityRegistry()

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=devices,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=list(devices.devices.values()),
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entities,
            ),
        ):
            _migrate_electricity_device(
                SimpleNamespace(),
                self.config_entry,
            )

        assert set(devices.devices) == {
            "legacy-device-1",
            "legacy-device-2",
        }
        assert legacy_device_one.identifiers == {
            (DOMAIN, "entry-id", None)
        }
        assert legacy_device_two.identifiers == {
            (DOMAIN, "entry-id", "legacy")
        }
