"""Tests for migrating Mijn Liander entity and device registry entries."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mijn_liander.const import DOMAIN
from custom_components.mijn_liander.migration import (
    _migrate_electricity_device,
    _migrate_entity_unique_ids,
    _process_single_entity_migration,
    remove_inactive_gas_registry_entries,
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
            entry for entry in self.values() if entry.config_entry_id == config_entry_id
        ]


class FakeEntityRegistry:
    """Small subset of the entity registry API."""

    def __init__(self, *entries: FakeEntity) -> None:
        """Initialize the fake entity registry."""
        self.entities = FakeEntityCollection(
            (entry.entity_id, entry) for entry in entries
        )

    def async_get(self, entity_id: str) -> FakeEntity | None:
        """Return an entity by entity ID through the public registry API."""
        return self.entities.get(entity_id)

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


class TestRegistryMigration:
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
        """Keep the current entity when its unique ID already exists."""
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

        assert registry.entities == {updated.entity_id: updated}

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
            if legacy_key != "contract"
        } | {duplicate.entity_id}

        for legacy_key, current_key in key_mappings.items():
            entity = (
                registry.entities[duplicate.entity_id]
                if legacy_key == "contract"
                else registry.entities[f"binary_sensor.liander_{legacy_key}"]
            )
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
        assert legacy_device.identifiers == {(DOMAIN, "entry-id", None)}
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
        assert legacy_device.identifiers == {(DOMAIN, "entry-id", None)}
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
        assert legacy_device_one.identifiers == {(DOMAIN, "entry-id", None)}
        assert legacy_device_two.identifiers == {(DOMAIN, "entry-id", "legacy")}


def test_analog_cleanup_is_isolated_and_idempotent() -> None:
    """Remove only deprecated analog entries owned by this integration and entry."""
    entries = [
        FakeEntity(
            "binary_sensor.old", "account.analog", "binary_sensor", DOMAIN, "entry"
        ),
        FakeEntity(
            "binary_sensor.current", "account_analog", "binary_sensor", DOMAIN, "entry"
        ),
        FakeEntity(
            "binary_sensor.other_account",
            "account_analog",
            "binary_sensor",
            DOMAIN,
            "other",
        ),
        FakeEntity(
            "binary_sensor.other_platform",
            "account_analog",
            "binary_sensor",
            "other",
            "entry",
        ),
        FakeEntity("sensor.unrelated", "account_analog", "sensor", DOMAIN, "entry"),
        FakeEntity(
            "binary_sensor.supported", "account_gprs", "binary_sensor", DOMAIN, "entry"
        ),
    ]
    registry = FakeEntityRegistry(*entries)
    entry = SimpleNamespace(unique_id="account", entry_id="entry")
    _migrate_entity_unique_ids(registry, entry)
    _migrate_entity_unique_ids(registry, entry)
    assert set(registry.entities) == {item.entity_id for item in entries[2:]}


@pytest.mark.parametrize("duplicate_missing", [True, False])
def test_reject_missing_or_foreign_duplicate(duplicate_missing: bool) -> None:
    """Reject unresolved and foreign duplicates without changing registry entries."""
    legacy = FakeEntity("sensor.legacy", "account.address", "sensor", DOMAIN, "entry")
    duplicate = FakeEntity(
        "sensor.current", "account_address", "sensor", DOMAIN, "other"
    )
    registry = FakeEntityRegistry(legacy, duplicate)
    config_entry = SimpleNamespace(unique_id="account", entry_id="entry")
    with (
        patch.object(
            registry,
            "async_get",
            return_value=None if duplicate_missing else duplicate,
        ),
        patch.object(registry, "async_remove") as remove,
        patch.object(registry, "async_update_entity") as update,
    ):
        assert not _process_single_entity_migration(
            registry, config_entry, legacy, "account", "account.", "account_", set()
        )
    remove.assert_not_called()
    update.assert_not_called()
    assert registry.entities == {"sensor.legacy": legacy, "sensor.current": duplicate}
    assert legacy.unique_id == "account.address"
    assert duplicate.unique_id == "account_address"


@pytest.mark.parametrize("current_first", [False, True])
@pytest.mark.parametrize(
    ("domain", "legacy_key", "current_key"),
    [
        ("sensor", "address", "address"),
        ("binary_sensor", "slimmeMeter", "smart_meter"),
    ],
)
async def test_duplicate_migration_preserves_registry_metadata(
    hass: HomeAssistant,
    domain: str,
    legacy_key: str,
    current_key: str,
    current_first: bool,
) -> None:
    """Retain current registry identity, settings, and device across repeated runs."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
    )
    if current_first:
        registry.async_get_or_create(
            domain,
            DOMAIN,
            f"account_{current_key}",
            config_entry=config_entry,
            suggested_object_id="duplicate",
        )
    legacy = registry.async_get_or_create(
        domain,
        DOMAIN,
        f"account.{legacy_key}",
        config_entry=config_entry,
        suggested_object_id="legacy",
        device_id=device.id,
    )
    legacy = registry.async_update_entity(
        legacy.entity_id,
        name="My meter",
        icon="mdi:flash",
        disabled_by=er.RegistryEntryDisabler.USER,
        hidden_by=er.RegistryEntryHider.USER,
        labels={"meter"},
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    registry.async_update_entity_options(
        legacy.entity_id, DOMAIN, {"custom_setting": "legacy"}
    )
    legacy = registry.async_get(legacy.entity_id)
    assert legacy is not None
    duplicate = registry.async_get_or_create(
        domain,
        DOMAIN,
        f"account_{current_key}",
        config_entry=config_entry,
        suggested_object_id="duplicate",
    )
    registry.async_update_entity(
        duplicate.entity_id,
        name="Duplicate meter",
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,
        hidden_by=er.RegistryEntryHider.USER,
        labels={"current"},
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    registry.async_update_entity_options(
        duplicate.entity_id, DOMAIN, {"custom_setting": "duplicate"}
    )

    duplicate = registry.async_get(duplicate.entity_id)
    assert duplicate is not None
    for _ in range(2):
        _migrate_entity_unique_ids(registry, config_entry)
        retained = registry.async_get(duplicate.entity_id)
        assert retained is not None
        assert retained.unique_id == f"account_{current_key}"
        for attribute in (
            "id",
            "entity_id",
            "name",
            "icon",
            "disabled_by",
            "hidden_by",
            "labels",
            "entity_category",
            "options",
            "device_id",
            "config_entry_id",
        ):
            assert getattr(retained, attribute) == getattr(duplicate, attribute)
        assert devices.async_get(retained.device_id) == device
        assert registry.async_get(legacy.entity_id) is None
        assert (
            registry.async_get_entity_id(domain, DOMAIN, f"account_{current_key}")
            == duplicate.entity_id
        )


@pytest.mark.parametrize("foreign_entity", [False, True])
async def test_duplicate_migration_allows_inactive_gas_cleanup(
    hass: HomeAssistant,
    foreign_entity: bool,
) -> None:
    """Remove owned gas duplicates and devices while preserving foreign entities."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{config_entry.entry_id}_Gas")},
        model="Gas",
    )
    legacy = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "account.gas_ean",
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id="legacy_gas",
    )
    current = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "account_gas_ean",
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id="current_gas",
    )
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    foreign = None
    if foreign_entity:
        foreign = registry.async_get_or_create(
            "sensor",
            "other",
            "foreign",
            config_entry=other,
            device_id=device.id,
        )
    for _ in range(2):
        _migrate_entity_unique_ids(registry, config_entry)
        remove_inactive_gas_registry_entries(hass, config_entry)
        assert registry.async_get(legacy.entity_id) is None
        assert registry.async_get(current.entity_id) is None
        if foreign is not None:
            assert registry.async_get(foreign.entity_id) == foreign
            assert devices.async_get(device.id) is not None
        else:
            assert devices.async_get(device.id) is None


@pytest.mark.parametrize("gas_device_exists", [False, True])
@pytest.mark.parametrize("on_other_device", [False, True])
@pytest.mark.parametrize("domain", ["sensor", "binary_sensor"])
async def test_inactive_gas_cleanup_uses_owned_unique_ids(
    hass: HomeAssistant,
    gas_device_exists: bool,
    on_other_device: bool,
    domain: str,
) -> None:
    """Remove owned gas IDs off the gas device, preserving electricity and foreign IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain=DOMAIN, unique_id="other-account")
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    electricity = devices.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        model="Elektra",
    )
    gas = None
    if gas_device_exists:
        gas = devices.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_Gas")},
            model="Gas",
        )
    gas_key = "gas_ean" if domain == "sensor" else "gas_smart_meter"
    current = registry.async_get_or_create(
        domain,
        DOMAIN,
        f"account_{gas_key}",
        config_entry=config_entry,
        device_id=electricity.id if on_other_device else None,
        suggested_object_id="current_gas",
    )
    legacy = registry.async_get_or_create(
        domain,
        DOMAIN,
        f"account.{gas_key}",
        config_entry=config_entry,
        device_id=gas.id if gas is not None else None,
        suggested_object_id="legacy_gas",
    )
    electric_entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "account_electricity_ean",
        config_entry=config_entry,
        device_id=electricity.id,
    )
    foreign = registry.async_get_or_create(
        domain,
        DOMAIN,
        "account_gas_foreign",
        config_entry=other_entry,
        device_id=electricity.id,
    )

    for _ in range(2):
        _migrate_entity_unique_ids(registry, config_entry)
        remove_inactive_gas_registry_entries(hass, config_entry)
        assert registry.async_get(current.entity_id) is None
        assert registry.async_get(legacy.entity_id) is None
        assert registry.async_get(electric_entity.entity_id) == electric_entity
        assert registry.async_get(foreign.entity_id) == foreign
        assert devices.async_get(electricity.id) is not None
        if gas is not None:
            assert devices.async_get(gas.id) is None


async def test_inactive_gas_cleanup_removes_dotted_ids_without_prior_migration(
    hass: HomeAssistant,
) -> None:
    """Recognize a legacy gas unique ID even if no device or current entry exists."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, "account.gas_ean", config_entry=config_entry
    )

    remove_inactive_gas_registry_entries(hass, config_entry)
    remove_inactive_gas_registry_entries(hass, config_entry)

    assert registry.async_get(legacy.entity_id) is None
