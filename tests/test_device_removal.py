"""Tests for native Home Assistant removal of Mijn Liander group devices."""

import pytest
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mijn_liander import async_remove_config_entry_device
from custom_components.mijn_liander.const import (
    DOMAIN,
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_GAS,
    SERVICE_NAME_USER,
)


@pytest.mark.parametrize(
    ("group_name", "identifier"),
    [
        (SERVICE_NAME_ELEKTRA, "{entry_id}"),
        (SERVICE_NAME_USER, "{entry_id}_Gebruiker"),
        (SERVICE_NAME_GAS, "{entry_id}_Gas"),
    ],
)
async def test_allow_removal_of_owned_group_device(
    hass, group_name: str, identifier: str
) -> None:
    """Allow Home Assistant to remove each known Mijn Liander group."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, identifier.format(entry_id=config_entry.entry_id))},
        model=group_name,
    )

    assert await async_remove_config_entry_device(
        hass, config_entry, device_entry
    )

    # Home Assistant removes the device after the integration approves it.
    device_registry.async_remove_device(device_entry.id)
    assert device_registry.async_get(device_entry.id) is None


async def test_reject_removal_of_unrelated_device(hass) -> None:
    """Reject devices that do not represent a Mijn Liander service group."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="other", unique_id="other")
    other_entry.add_to_hass(hass)
    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "router")},
        model="Router",
    )

    assert not await async_remove_config_entry_device(
        hass, config_entry, device_entry
    )
    assert dr.async_get(hass).async_get(device_entry.id) is not None


async def test_reject_group_with_unexpected_identifier(hass) -> None:
    """Reject a group model if its identifier does not belong to this entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="account")
    config_entry.add_to_hass(hass)
    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "another-entry_Gas")},
        model=SERVICE_NAME_GAS,
    )

    assert not await async_remove_config_entry_device(
        hass, config_entry, device_entry
    )
    assert dr.async_get(hass).async_get(device_entry.id) is not None
