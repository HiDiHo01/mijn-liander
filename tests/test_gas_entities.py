"""Tests for conditional Mijn Liander gas entities."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.mijn_liander import _async_monitor_gas_contract
from custom_components.mijn_liander.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from custom_components.mijn_liander.const import DOMAIN, SERVICE_NAME_GAS
from custom_components.mijn_liander.gas import (
    filter_entity_descriptions,
    has_active_gas_contract,
)
from custom_components.mijn_liander.migration import (
    remove_inactive_gas_registry_entries,
)
from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS


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
    identifiers: set[tuple[str, str]]
    model: str
    config_entries: set[str]


class FakeEntityCollection(dict[str, FakeEntity]):
    """Minimal entity registry collection."""


class FakeEntityRegistry:
    """Minimal entity registry."""

    def __init__(self, *entities: FakeEntity) -> None:
        self.entities = FakeEntityCollection(
            (entity.entity_id, entity) for entity in entities
        )

    def async_remove(self, entity_id: str) -> None:
        self.entities.pop(entity_id)


class FakeDeviceRegistry:
    """Minimal device registry."""

    def __init__(self, *devices: FakeDevice) -> None:
        self.devices = {device.id: device for device in devices}

    def async_remove_device(self, device_id: str) -> None:
        self.devices.pop(device_id)


class GasEntityTests(unittest.TestCase):
    """Verify gas contract detection and registry cleanup."""

    def test_only_active_gas_contract_counts_as_available(self) -> None:
        """Missing, malformed, or inactive gas contracts do not qualify."""
        for data in (
            None,
            {},
            [],
            [{}],
            [{"aansluitingen": {"gas": []}}],
            gas_data(False),
            gas_data(None),
            [{"aansluitingen": {"gas": [{"contract": "false"}]}}],
        ):
            with self.subTest(data=data):
                self.assertFalse(has_active_gas_contract(data))

        self.assertTrue(has_active_gas_contract(gas_data()))

    def test_gas_descriptions_are_filtered_for_electricity_only_accounts(
        self,
    ) -> None:
        """Electricity and account entities remain; gas entities are omitted."""
        sensors = filter_entity_descriptions(SENSOR_DESCRIPTIONS, gas_data(False))
        binary_sensors = filter_entity_descriptions(
            BINARY_SENSOR_DESCRIPTIONS, gas_data(False)
        )

        self.assertEqual(len(sensors), 12)
        self.assertEqual(len(binary_sensors), 12)
        self.assertTrue(
            all(description.service_name != SERVICE_NAME_GAS for description in sensors)
        )
        self.assertTrue(
            all(
                description.service_name != SERVICE_NAME_GAS
                for description in binary_sensors
            )
        )

    def test_all_gas_descriptions_are_kept_for_active_contract(self) -> None:
        """An active gas contract retains all gas sensors and binary sensors."""
        sensors = filter_entity_descriptions(SENSOR_DESCRIPTIONS, gas_data())
        binary_sensors = filter_entity_descriptions(
            BINARY_SENSOR_DESCRIPTIONS, gas_data()
        )

        self.assertEqual(len(sensors), len(SENSOR_DESCRIPTIONS))
        self.assertEqual(len(binary_sensors), len(BINARY_SENSOR_DESCRIPTIONS))
        self.assertEqual(
            sum(item.service_name == SERVICE_NAME_GAS for item in sensors), 7
        )
        self.assertEqual(
            sum(item.service_name == SERVICE_NAME_GAS for item in binary_sensors),
            5,
        )

    def test_remove_gas_registry_entries_when_contract_is_absent(self) -> None:
        """Remove old gas entities and their now-unused dedicated device."""
        entry = SimpleNamespace(entry_id="entry-id")
        device = FakeDevice(
            id="gas-device",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id"},
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
                "custom_components.mijn_liander.migration.device_registry.async_entries_for_config_entry",
                return_value=[device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(SimpleNamespace(), entry)

        self.assertEqual(entity_registry.entities, {})
        self.assertEqual(device_registry.devices, {})

    def test_gas_cleanup_preserves_shared_device_and_other_entities(self) -> None:
        """Do not delete a gas device still used by another config entry."""
        entry = SimpleNamespace(entry_id="entry-id")
        device = FakeDevice(
            id="gas-device",
            identifiers={(DOMAIN, f"entry-id_{SERVICE_NAME_GAS}")},
            model=SERVICE_NAME_GAS,
            config_entries={"entry-id", "other-entry"},
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
        entity_registry = FakeEntityRegistry(own_entity, other_entity)

        with (
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_get",
                return_value=device_registry,
            ),
            patch(
                "custom_components.mijn_liander.migration.device_registry.async_entries_for_config_entry",
                return_value=[device],
            ),
            patch(
                "custom_components.mijn_liander.migration.entity_registry.async_get",
                return_value=entity_registry,
            ),
        ):
            remove_inactive_gas_registry_entries(SimpleNamespace(), entry)

        self.assertEqual(
            set(entity_registry.entities),
            {"sensor.other"},
        )
        self.assertEqual(set(device_registry.devices), {"gas-device"})


class GasContractMonitorTests(unittest.IsolatedAsyncioTestCase):
    """Verify gas contract changes reload platform entity descriptions."""

    async def test_reload_when_gas_contract_is_added_or_removed(self) -> None:
        """Reload when refreshed data changes gas entity availability."""
        listener = None

        def add_listener(callback):
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

        _async_monitor_gas_contract(hass, entry, coordinator, False)
        coordinator.data = gas_data()
        listener()
        await asyncio.sleep(0)

        reload.assert_awaited_once_with("entry-id")

        coordinator.data = gas_data(False)
        listener()
        await asyncio.sleep(0)

        self.assertEqual(reload.await_count, 2)


if __name__ == "__main__":
    unittest.main()
