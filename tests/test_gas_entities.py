"""Tests for conditional Mijn Liander gas entities."""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.mijn_liander import _async_monitor_gas_contract
from custom_components.mijn_liander.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    LianderBinarySensor,
)
from custom_components.mijn_liander.const import DOMAIN, SERVICE_NAME_GAS
from custom_components.mijn_liander.gas import (
    filter_entity_descriptions,
    get_active_gas_connection,
    has_active_gas_contract,
)
from custom_components.mijn_liander.migration import (
    remove_inactive_gas_registry_entries,
)
from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS, LianderSensor


def gas_data(contract: object = True) -> list[dict[str, object]]:
    """Return a coordinator payload containing one gas connection."""
    return [
        {
            "aansluitingen": {
                "elektra": [{"status": "In bedrijf"}],
                "gas": [{"contract": contract}],
            }
        }
    ]


@dataclass
class FakeEntity:
    """Entity registry entry used by gas cleanup tests."""

    entity_id: str
    platform: str
    config_entry_id: str
    device_id: str


@dataclass
class FakeDevice:
    """Device registry entry used by gas cleanup tests."""

    id: str
    identifiers: set[tuple[object, ...]]
    model: str
    config_entries: set[str]
    config_entry_id: str


class FakeEntityCollection(dict[str, FakeEntity]):
    """Minimal entity registry collection."""


class FakeEntityRegistry:
    """Minimal entity registry."""

    def __init__(self, *entities: FakeEntity) -> None:
        """Initialize the fake entity registry."""
        self.entities = FakeEntityCollection(
            (entity.entity_id, entity) for entity in entities
        )

    def async_remove(self, entity_id: str) -> None:
        """Remove an entity from the fake registry."""
        self.entities.pop(entity_id)


class FakeDeviceRegistry:
    """Minimal device registry."""

    def __init__(self, *devices: FakeDevice) -> None:
        """Initialize the fake device registry."""
        self.devices = {device.id: device for device in devices}

    def async_remove_device(self, device_id: str) -> None:
        """Remove a device from the fake registry."""
        self.devices.pop(device_id)


class GasEntityTests:
    """Verify gas contract detection and registry cleanup."""

    def test_only_active_gas_contract_counts_as_available(self) -> None:
        """Missing, malformed, or inactive gas contracts do not qualify."""
        invalid_data = (
            None,
            {},
            [],
            [{}],
            [{"aansluitingen": {"gas": []}}],
            gas_data(False),
            gas_data(None),
            [{"aansluitingen": {"gas": [{"contract": "false"}]}}],
        )

        for data in invalid_data:
            assert not has_active_gas_contract(data)

        assert has_active_gas_contract(gas_data())

    def test_entities_use_the_first_active_gas_connection(self) -> None:
        """Ignore earlier inactive connections consistently across gas entities."""
        data = [
            {
                "aansluitingen": {
                    "gas": [
                        {"contract": False, "ean": "inactive-ean"},
                        {
                            "contract": True,
                            "ean": "active-ean",
                            "status": "In bedrijf",
                        },
                    ]
                }
            }
        ]
        active_connection = data[0]["aansluitingen"]["gas"][1]

        assert get_active_gas_connection(data) is active_connection

        sensor = SimpleNamespace(
            coordinator=SimpleNamespace(data=data),
            entity_description=next(
                item for item in SENSOR_DESCRIPTIONS if item.key == "gas_ean"
            ),
        )
        binary_sensor = SimpleNamespace(
            coordinator=SimpleNamespace(data=data),
            entity_description=next(
                item
                for item in BINARY_SENSOR_DESCRIPTIONS
                if item.key == "gas_contract_active"
            ),
        )

        assert LianderSensor.native_value.fget(sensor) == "active-ean"
        assert LianderBinarySensor._get_is_on(binary_sensor)

    def test_gas_descriptions_are_filtered_for_electricity_only_accounts(
        self,
    ) -> None:
        """Keep electricity/account entities and omit gas entities."""
        sensors = filter_entity_descriptions(
            SENSOR_DESCRIPTIONS,
            gas_data(False),
        )
        binary_sensors = filter_entity_descriptions(
            BINARY_SENSOR_DESCRIPTIONS,
            gas_data(False),
        )

        assert len(sensors) == 12
        assert len(binary_sensors) == 12

        assert all(
            description.service_name != SERVICE_NAME_GAS
            for description in sensors
        )
        assert all(
            description.service_name != SERVICE_NAME_GAS
            for description in binary_sensors
        )

    def test_all_gas_descriptions_are_kept_for_active_contract(self) -> None:
        """Keep all gas sensors and binary sensors for an active contract."""
        sensors = filter_entity_descriptions(
            SENSOR_DESCRIPTIONS,
            gas_data(),
        )
        binary_sensors = filter_entity_descriptions(
            BINARY_SENSOR_DESCRIPTIONS,
            gas_data(),
        )

        assert len(sensors) == len(SENSOR_DESCRIPTIONS)
        assert len(binary_sensors) == len(BINARY_SENSOR_DESCRIPTIONS)

        assert sum(
            item.service_name == SERVICE_NAME_GAS for item in sensors
        ) == 7
        assert sum(
            item.service_name == SERVICE_NAME_GAS
            for item in binary_sensors
        ) == 5

    def test_remove_gas_registry_entries_when_contract_is_absent(self) -> None:
        """Remove gas entities and their now-unused dedicated device."""
        entry = SimpleNamespace(entry_id="entry-id")

        device = FakeDevice(
            id="gas-device",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )

        device_registry = FakeDeviceRegistry(device)

        entity_registry = FakeEntityRegistry(
            *(
                FakeEntity(
                    entity_id=f"sensor.gas_{index}",
                    platform=DOMAIN,
                    config_entry_id="entry-id",
                    device_id="gas-device",
                )
                for index in range(7)
            ),
            *(
                FakeEntity(
                    entity_id=f"binary_sensor.gas_{index}",
                    platform=DOMAIN,
                    config_entry_id="entry-id",
                    device_id="gas-device",
                )
                for index in range(5)
            ),
        )

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=device_registry,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=[device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(
                SimpleNamespace(),
                entry,
            )

        assert entity_registry.entities == {}
        assert device_registry.devices == {}

    def test_gas_cleanup_preserves_shared_device_and_other_entities(
        self,
    ) -> None:
        """Keep a gas device that still contains another integration entity."""
        entry = SimpleNamespace(entry_id="entry-id")

        device = FakeDevice(
            id="gas-device",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id", "other-entry"},
            config_entry_id="entry-id",
        )

        own_entity = FakeEntity(
            entity_id="sensor.gas_own",
            platform=DOMAIN,
            config_entry_id="entry-id",
            device_id="gas-device",
        )
        other_entity = FakeEntity(
            entity_id="sensor.other",
            platform="other_integration",
            config_entry_id="other-entry",
            device_id="gas-device",
        )

        device_registry = FakeDeviceRegistry(device)
        entity_registry = FakeEntityRegistry(
            own_entity,
            other_entity,
        )

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=device_registry,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=[device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(
                SimpleNamespace(),
                entry,
            )

        assert set(entity_registry.entities) == {"sensor.other"}
        assert set(device_registry.devices) == {"gas-device"}

    def test_gas_cleanup_preserves_device_owned_by_another_config_entry(
        self,
    ) -> None:
        """Keep a gas device whose owning config entry is different."""
        entry = SimpleNamespace(entry_id="entry-id")

        device = FakeDevice(
            id="gas-device",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id", "other-entry"},
            config_entry_id="other-entry",
        )

        own_entity = FakeEntity(
            entity_id="sensor.gas_own",
            platform=DOMAIN,
            config_entry_id="entry-id",
            device_id="gas-device",
        )

        device_registry = FakeDeviceRegistry(device)
        entity_registry = FakeEntityRegistry(own_entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=device_registry,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=[device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(
                SimpleNamespace(),
                entry,
            )

        assert entity_registry.entities == {}
        assert set(device_registry.devices) == {"gas-device"}

    def test_gas_cleanup_preserves_multiple_gas_devices(self) -> None:
        """Leave multiple gas devices untouched to avoid ambiguous cleanup."""
        entry = SimpleNamespace(entry_id="entry-id")

        first_device = FakeDevice(
            id="gas-device-1",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )
        second_device = FakeDevice(
            id="gas-device-2",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id"},
            config_entry_id="entry-id",
        )

        entity = FakeEntity(
            entity_id="sensor.gas",
            platform=DOMAIN,
            config_entry_id="entry-id",
            device_id="gas-device-1",
        )

        device_registry = FakeDeviceRegistry(
            first_device,
            second_device,
        )
        entity_registry = FakeEntityRegistry(entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=device_registry,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry."
                "async_entries_for_config_entry",
                return_value=[first_device, second_device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(
                SimpleNamespace(),
                entry,
            )

        assert set(device_registry.devices) == {
            "gas-device-1",
            "gas-device-2",
        }
        assert set(entity_registry.entities) == {"sensor.gas"}


class GasContractMonitorTests:
    """Verify gas contract changes reload platform entity descriptions."""

    async def test_reload_when_gas_contract_is_added_or_removed(self) -> None:
        """Reload when refreshed data changes gas entity availability."""
        listener = None

        def add_listener(callback):
            """Register the coordinator listener."""
            nonlocal listener
            listener = callback
            return lambda: None

        coordinator = SimpleNamespace(
            data=[{"aansluitingen": {"gas": []}}],
            async_add_listener=add_listener,
        )
        entry = SimpleNamespace(
            entry_id="entry-id",
            async_on_unload=lambda callback: None,
        )
        reload = AsyncMock(return_value=True)
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(async_reload=reload),
            async_create_task=asyncio.create_task,
        )

        _async_monitor_gas_contract(
            hass,
            entry,
            coordinator,
            False,
        )

        assert listener is not None

        coordinator.data = gas_data()
        listener()
        await asyncio.sleep(0)

        reload.assert_awaited_once_with("entry-id")

        coordinator.data = gas_data(False)
        listener()
        await asyncio.sleep(0)

        assert reload.await_count == 2
