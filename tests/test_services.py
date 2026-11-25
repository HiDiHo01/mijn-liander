"""Tests for Mijn Liander group removal service."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.mijn_liander.const import DOMAIN
from custom_components.mijn_liander.services import SERVICE_REMOVE_GROUP


async def test_remove_group_only_removes_selected_group(hass, config_entry) -> None:
    """Remove selected group entities without touching another group or integration."""
    config_entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    gas_device = devices.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{config_entry.entry_id}_Gas")},
        model="Gas",
    )
    electricity_device = devices.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        model="Elektra",
    )
    gas_entity = entities.async_get_or_create(
        "sensor",
        DOMAIN,
        "account_gas_ean",
        config_entry=config_entry,
        device_id=gas_device.id,
    )
    electricity_entity = entities.async_get_or_create(
        "sensor",
        DOMAIN,
        "account_electricity_ean",
        config_entry=config_entry,
        device_id=electricity_device.id,
    )

    await async_setup_component(hass, DOMAIN, {})
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_GROUP,
        {"device_id": gas_device.id},
        blocking=True,
    )

    assert entities.async_get(gas_entity.entity_id) is None
    assert entities.async_get(electricity_entity.entity_id) is not None
    assert devices.async_get(gas_device.id) is None
    assert devices.async_get(electricity_device.id) is not None
