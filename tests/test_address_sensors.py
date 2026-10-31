"""Verify separate address sensors and their shared account/device identity."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import PlatformData
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.mijn_liander.const import DOMAIN, SERVICE_NAME_USER
from custom_components.mijn_liander.gas import filter_entity_descriptions
from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS, LianderSensor

ADDRESS_CASES = (
    ("postal_code", "postcode", "0123 AB", "Postcode", "Postal code"),
    ("street", "straat", "Teststraat", "Straat", "Street"),
    ("house_number", "huisnummer", "12", "Huisnummer", "House number"),
    (
        "house_number_addition",
        "toevoeging",
        "A",
        "Toevoeging",
        "House number addition",
    ),
    ("city", "plaats", "Teststad", "Plaats", "City"),
)
ADDRESS_KEYS = (
    "postal_code",
    "street",
    "house_number",
    "house_number_addition",
    "city",
)
INTEGRATION_PATH = Path(__file__).parents[1] / "custom_components" / DOMAIN


def _address_data() -> list[dict[str, object]]:
    """Return a synthetic address without requiring electricity or gas data."""
    return [
        {
            "adres": {
                "postcode": "0123 AB",
                "straat": "Teststraat",
                "huisnummer": 12,
                "toevoeging": "A",
                "plaats": "Teststad",
            }
        }
    ]


def _make_sensor(
    sensor_key: str, data: object, account_id: str = "test-account"
) -> LianderSensor:
    """Create an address sensor with a distinct synthetic account identity."""
    description = next(item for item in SENSOR_DESCRIPTIONS if item.key == sensor_key)
    entry = MagicMock(unique_id=account_id, entry_id=f"{account_id}-entry")
    sensor = LianderSensor(MagicMock(data=data), description, entry)
    sensor.platform_data = PlatformData(
        MagicMock(), domain="sensor", platform_name=DOMAIN
    )
    return sensor


@pytest.mark.parametrize(
    ("sensor_key", "api_field", "expected_value", "dutch_name", "english_name"),
    ADDRESS_CASES,
)
def test_address_fields_share_user_device_and_translations(
    sensor_key: str,
    api_field: str,
    expected_value: str,
    dutch_name: str,
    english_name: str,
) -> None:
    """Expose each requested field as translated text on the existing User device."""
    data = _address_data()
    sensor = _make_sensor(sensor_key, data)
    combined_sensor = _make_sensor("address", data)

    assert sensor.native_value == expected_value
    assert sensor.state == expected_value
    assert sensor.entity_description.service_name == SERVICE_NAME_USER
    assert sensor.device_info == combined_sensor.device_info
    assert sensor.unique_id == f"test-account_{sensor_key}"
    assert sensor.native_unit_of_measurement is None
    assert sensor.device_class is None
    assert sensor.entity_description.entity_registry_enabled_default
    assert api_field in data[0]["adres"]

    for relative_path, expected_name in (
        ("strings.json", english_name),
        ("translations/en.json", english_name),
        ("translations/nl.json", dutch_name),
    ):
        translations = json.loads(
            (INTEGRATION_PATH / relative_path).read_text(encoding="utf-8")
        )
        assert translations["entity"]["sensor"][sensor_key]["name"] == expected_name


@pytest.mark.parametrize("sensor_key", ADDRESS_KEYS)
@pytest.mark.parametrize(
    "data",
    [None, [], {}, [None, {}], [{"adres": None}], [{"adres": []}], [{"adres": {}}]],
)
def test_missing_address_data_is_unknown(sensor_key: str, data: object) -> None:
    """Missing or malformed addresses must not create fabricated field values."""
    sensor = _make_sensor(sensor_key, data)

    assert sensor.native_value is None
    assert sensor.state is None


@pytest.mark.parametrize(
    ("sensor_key", "api_field"),
    [(case[0], case[1]) for case in ADDRESS_CASES],
)
@pytest.mark.parametrize("invalid_value", [None, True, 12.5, {}, []])
def test_invalid_address_fields_are_unknown(
    sensor_key: str,
    api_field: str,
    invalid_value: object,
) -> None:
    """Reject invalid field types without stringifying containers or booleans."""
    sensor = _make_sensor(sensor_key, [{"adres": {api_field: invalid_value}}])

    assert sensor.native_value is None


def test_address_format_and_text_values_are_preserved() -> None:
    """Keep the combined address format, house-number zeros, and empty additions."""
    assert _make_sensor("address", _address_data()).native_value == (
        "Teststraat 12A 0123 AB Teststad"
    )
    assert (
        _make_sensor("house_number", [{"adres": {"huisnummer": "0012"}}]).native_value
        == "0012"
    )
    assert (
        _make_sensor("house_number", [{"adres": {"huisnummer": 0}}]).native_value == "0"
    )
    assert (
        _make_sensor(
            "house_number_addition", [{"adres": {"toevoeging": ""}}]
        ).native_value
        == ""
    )


@pytest.mark.parametrize("sensor_key", ADDRESS_KEYS)
def test_address_fields_do_not_mix_accounts(sensor_key: str) -> None:
    """Use the same first address as the combined sensor and isolate config entries."""
    assert (
        _make_sensor(sensor_key, [{"adres": {}}, *_address_data()]).native_value is None
    )
    first_sensor = _make_sensor(sensor_key, _address_data(), account_id="first-account")
    second_sensor = _make_sensor(
        sensor_key, [{"adres": {}}], account_id="second-account"
    )

    assert first_sensor.native_value is not None
    assert second_sensor.native_value is None
    assert first_sensor.unique_id != second_sensor.unique_id
    assert first_sensor.device_info["identifiers"].isdisjoint(
        second_sensor.device_info["identifiers"]
    )


def test_user_address_sensors_are_kept_without_gas() -> None:
    """Include all five new sensors and the existing address without a gas contract."""
    descriptions = filter_entity_descriptions(SENSOR_DESCRIPTIONS, _address_data())
    user_keys = {
        item.key for item in descriptions if item.service_name == SERVICE_NAME_USER
    }

    assert user_keys == {"address", *ADDRESS_KEYS}


async def test_address_states_follow_coordinator_updates(hass: HomeAssistant) -> None:
    """Update all six user address entities through the actual coordinator listener."""
    logger = logging.getLogger(__name__)
    coordinator = DataUpdateCoordinator(hass, logger, name=DOMAIN, config_entry=None)
    coordinator.async_set_updated_data(_address_data())
    entry = MagicMock(unique_id="test-account", entry_id="test-entry")
    sensors = [
        LianderSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
        if description.service_name == SERVICE_NAME_USER
    ]
    for sensor in sensors:
        sensor.entity_id = f"sensor.test_{sensor.entity_description.key}"
    component = EntityComponent(logger, "sensor", hass)
    await component.async_add_entities(sensors)
    await hass.async_block_till_done()
    initial_state = hass.states.get("sensor.test_address")
    assert initial_state is not None
    assert initial_state.state == "Teststraat 12A 0123 AB Teststad"

    coordinator.async_set_updated_data(
        [
            {
                "adres": {
                    "postcode": "4567 CD",
                    "straat": "Anderestraat",
                    "huisnummer": 34,
                    "toevoeging": "",
                    "plaats": "Andereplaats",
                }
            }
        ]
    )
    await hass.async_block_till_done()
    expected_states = {
        "address": "Anderestraat 34 4567 CD Andereplaats",
        "postal_code": "4567 CD",
        "street": "Anderestraat",
        "house_number": "34",
        "house_number_addition": "",
        "city": "Andereplaats",
    }
    for sensor_key, expected_state in expected_states.items():
        state = hass.states.get(f"sensor.test_{sensor_key}")
        assert state is not None
        assert state.state == expected_state

    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    for sensor_key in expected_states:
        state = hass.states.get(f"sensor.test_{sensor_key}")
        assert state is not None
        assert state.state == "unknown"
