"""Exercise sensor states and privacy using a fully synthetic Liander response."""

import json
import logging
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import PlatformData
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mijn_liander.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    LianderBinarySensor,
)
from custom_components.mijn_liander.const import DOMAIN, SERVICE_NAME_ELEKTRA
from custom_components.mijn_liander.coordinator import LianderDataUpdateCoordinator
from custom_components.mijn_liander.data import get_connection, get_mapping_list
from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS, LianderSensor

SENSOR_VALUES = {
    "address": "Voorbeeldstraat 10 0000 XX TESTPLAATS",
    "postal_code": "0000 XX",
    "street": "Voorbeeldstraat",
    "house_number": "10",
    "house_number_addition": "",
    "city": "TESTPLAATS",
    "electricity_ean": "000000000000000001",
    "connection_capacity": "3x25A",
    "network_costs": 500.0,
    "maximum_power": 17.2,
    "number_of_meters": 1,
    "meter_number": "TEST-ELECTRIC-001",
    "number_of_registers": 4,
    "number_of_phases": "3",
    "feed_in_start_date": datetime(2024, 1, 2, tzinfo=UTC),
    "generation_installations": 1,
    "storage_installations": 0,
    "generation_power": 4.0,
    "solar_panel_power": 4.4,
    "meter_type": "Elektrameter",
    "contractless_cases": 0,
    "gas_ean": "000000000000000002",
    "gas_connection_capacity": "G6",
    "gas_network_costs": 250.0,
    "gas_maximum_capacity": 10,
    "gas_number_of_meters": 1,
    "gas_meter_number": "TEST-GAS-001",
    "gas_number_of_registers": 1,
    "gas_meter_type": "Gasmeter",
    "gas_contractless_cases": 0,
}
BINARY_VALUES = {
    "status": True,
    "contract_active": True,
    "permission_to_read_data": True,
    "smart_meter": True,
    "gprs": False,
    "suitable_for_backfeeding": True,
    "suitable_for_dual_tariff": True,
    "backfeeding_energy": True,
    "meter_fault_check_allowed": True,
    "smart_meter_request_allowed": True,
    "net_metering": False,
    "gas_status": True,
    "gas_contract_active": True,
    "gas_permission_to_read_data": True,
    "gas_meter_fault_check_allowed": True,
    "gas_smart_meter": True,
}


@pytest.fixture
def api_data() -> list[dict[str, object]]:
    """Load fresh synthetic data so mutations never leak between tests."""
    path = Path(__file__).parent / "fixtures" / "liander_account.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _connection(
    data: list[dict[str, object]], kind: str = "elektra"
) -> dict[str, object]:
    """Select a connection from the known synthetic fixture schema."""
    return data[0]["aansluitingen"][kind][0]


def _entity(
    data: object, sensor_key: str, *, binary: bool = False
) -> LianderSensor | LianderBinarySensor:
    """Build a sensor using synthetic coordinator and config-entry identities."""
    descriptions = BINARY_SENSOR_DESCRIPTIONS if binary else SENSOR_DESCRIPTIONS
    description = next(item for item in descriptions if item.key == sensor_key)
    entity_class = LianderBinarySensor if binary else LianderSensor
    entity = entity_class(
        MagicMock(data=data),
        description,
        MagicMock(unique_id="synthetic-account", entry_id="synthetic-entry"),
    )
    entity.platform_data = PlatformData(
        MagicMock(),
        domain="binary_sensor" if binary else "sensor",
        platform_name=DOMAIN,
    )
    return entity


@pytest.mark.parametrize("sensor_key", SENSOR_VALUES)
def test_all_sensor_states_from_synthetic_response(
    api_data: list[dict[str, object]], sensor_key: str
) -> None:
    """Verify every declared sensor through Home Assistant state validation."""
    entity = _entity(api_data, sensor_key)
    expected = SENSOR_VALUES[sensor_key]
    assert type(entity.native_value) is type(expected)
    if isinstance(expected, float):
        assert entity.native_value == pytest.approx(expected)
        assert entity.state == pytest.approx(expected)
    else:
        assert entity.native_value == expected
        assert entity.state == (
            expected.isoformat() if isinstance(expected, datetime) else expected
        )


def test_fixture_covers_all_descriptions() -> None:
    """Require expected values for every scalar and binary description."""
    assert {item.key for item in SENSOR_DESCRIPTIONS} == set(SENSOR_VALUES)
    assert {item.key for item in BINARY_SENSOR_DESCRIPTIONS} == set(BINARY_VALUES)


@pytest.mark.parametrize("malformed", [None, "invalid", 42, []])
@pytest.mark.parametrize("before_valid", [False, True])
def test_malformed_connection_siblings_preserve_the_selected_account(
    api_data: list[dict[str, object]], malformed: object, before_valid: bool
) -> None:
    """Skip invalid sibling records without switching either platform to another account."""
    selected = _connection(api_data)
    siblings = [malformed, selected] if before_valid else [selected, malformed]
    api_data[0]["aansluitingen"]["elektra"] = siblings
    fallback = deepcopy(selected)
    fallback["maximaalVermogen"] = "99,9"
    fallback["meters"][0]["gprs"] = True
    api_data.append({"aansluitingen": {"elektra": [fallback]}})

    assert _entity(api_data, "maximum_power").native_value == pytest.approx(17.2)
    assert _entity(api_data, "gprs", binary=True).is_on is False
    assert get_connection(api_data, SERVICE_NAME_ELEKTRA) is selected


@pytest.mark.parametrize("before_valid", [False, True])
def test_malformed_connection_sibling_does_not_make_entities_unknown(
    api_data: list[dict[str, object]], before_valid: bool
) -> None:
    """Keep valid electricity readings when there is no later account to fall back to."""
    selected = _connection(api_data)
    siblings = [None, selected] if before_valid else [selected, None]
    api_data[0]["aansluitingen"]["elektra"] = siblings

    assert _entity(api_data, "maximum_power").state == pytest.approx(17.2)
    assert _entity(api_data, "gprs", binary=True).is_on is False
    assert get_mapping_list(siblings) is None


@pytest.mark.parametrize("kind", ["elektra", "gas"])
@pytest.mark.parametrize("malformed", [None, "invalid", 42, []])
def test_later_malformed_meters_do_not_hide_the_selected_meter(
    api_data: list[dict[str, object]], kind: str, malformed: object
) -> None:
    """Retain first-meter values and flags without publishing a partial meter count."""
    connection = _connection(api_data, kind)
    connection["meters"].append(malformed)
    prefix = "gas_" if kind == "gas" else ""

    assert _entity(api_data, f"{prefix}meter_number").state == (
        "TEST-GAS-001" if kind == "gas" else "TEST-ELECTRIC-001"
    )
    assert _entity(api_data, f"{prefix}number_of_registers").state == (
        1 if kind == "gas" else 4
    )
    assert _entity(api_data, f"{prefix}smart_meter", binary=True).is_on is True
    assert _entity(api_data, f"{prefix}number_of_meters").native_value is None
    if kind == "elektra":
        assert _entity(api_data, "number_of_phases").state == "3"
        assert _entity(api_data, "gprs", binary=True).is_on is False


@pytest.mark.parametrize("kind", ["elektra", "gas"])
def test_invalid_first_meter_is_not_replaced_by_a_later_meter(
    api_data: list[dict[str, object]], kind: str
) -> None:
    """Keep the established first-meter selection when its record is malformed."""
    connection = _connection(api_data, kind)
    connection["meters"].insert(0, None)
    prefix = "gas_" if kind == "gas" else ""

    assert _entity(api_data, f"{prefix}meter_number").state is None
    assert _entity(api_data, f"{prefix}smart_meter", binary=True).is_on is None


@pytest.mark.parametrize("sensor_key", BINARY_VALUES)
def test_initial_binary_states_are_not_truthiness_defaults(
    api_data: list[dict[str, object]], sensor_key: str
) -> None:
    """Honor explicit booleans on initialization."""
    entity = _entity(api_data, sensor_key, binary=True)
    assert entity.is_on is BINARY_VALUES[sensor_key]
    assert set(entity.extra_state_attributes) == {"attribution"}


def test_fixture_has_only_fictional_identifiers(
    api_data: list[dict[str, object]],
) -> None:
    """Verify synthetic naming conventions and consistent nested EAN references."""
    assert api_data[0]["adres"] == {
        "postcode": "0000 XX",
        "straat": "Voorbeeldstraat",
        "huisnummer": "10",
        "toevoeging": "",
        "plaats": "TESTPLAATS",
    }
    for kind, ean in (("elektra", "000000000000000001"), ("gas", "000000000000000002")):
        connection = _connection(api_data, kind)
        assert connection["ean"] == ean
        assert connection["meters"][0]["meternummer"].startswith("TEST-")
    installation = _connection(api_data)["opwekinstallaties"][0]
    assert installation["ean"] == _connection(api_data)["ean"]
    assert installation["eanOpwekinstallatie"] == "000000000000000003"
    assert installation["merkOmvormer"] == "Testmerk"
    assert installation["typeOmvormer"] == "Testmodel"
    assert installation["registratiedatum"].startswith("2024-01-01")


@pytest.mark.parametrize("value", ["false", "true", 0, 1, [], {}, None])
def test_non_boolean_flags_are_unknown(
    api_data: list[dict[str, object]], value: object
) -> None:
    """Do not turn strings or integers into plausible binary states."""
    connection = _connection(api_data)
    connection["toestemmingVoorUitlezen"] = value
    connection["meters"][0]["gprs"] = value
    assert _entity(api_data, "permission_to_read_data", binary=True).is_on is None
    assert _entity(api_data, "gprs", binary=True).is_on is None


@pytest.mark.parametrize("sensor_key", ["generation_power", "solar_panel_power"])
@pytest.mark.parametrize("invalid", [None, "bad", True, float("nan"), float("inf"), -1])
def test_generation_totals_never_publish_partial_ratings(
    api_data: list[dict[str, object]], sensor_key: str, invalid: object
) -> None:
    """One invalid installation invalidates its whole power aggregate."""
    connection = _connection(api_data)
    second = deepcopy(connection["opwekinstallaties"][0])
    field = (
        "vermogenOpwekinstallatie"
        if sensor_key == "generation_power"
        else "vermogenZonnepanelen"
    )
    second[field] = invalid
    connection["opwekinstallaties"].append(second)
    assert _entity(api_data, sensor_key).native_value is None


def test_generation_aggregates_and_allowlisted_details(
    api_data: list[dict[str, object]],
) -> None:
    """Sum all registrations and expose only the documented installation fields."""
    connection = _connection(api_data)
    expected_details = deepcopy(connection["opwekinstallaties"])
    connection["opwekinstallaties"][0]["privateNote"] = "TEST-PRIVATE-NOTE"
    assert _entity(api_data, "generation_installations").extra_state_attributes == {
        "installations": expected_details
    }
    second = deepcopy(expected_details[0])
    second["vermogenOpwekinstallatie"] = 5.0
    second["vermogenZonnepanelen"] = 5.5
    connection["opwekinstallaties"].append(second)
    assert _entity(api_data, "generation_power").native_value == pytest.approx(9.0)
    assert _entity(api_data, "solar_panel_power").native_value == pytest.approx(9.9)
    assert _entity(api_data, "generation_installations").native_value == 2
    second["maxVermogenEenheid"] = "W"
    assert _entity(api_data, "generation_power").native_value is None


@pytest.mark.parametrize("collection", [None, {}, "invalid", [None]])
def test_malformed_collections_are_not_empty_counts(
    api_data: list[dict[str, object]], collection: object
) -> None:
    """Do not report zero counts for missing or malformed installation/meter lists."""
    connection = _connection(api_data)
    for field in (
        "opwekinstallaties",
        "opslaginstallaties",
        "meters",
        "contractloosCases",
    ):
        connection[field] = collection
    for key in (
        "generation_installations",
        "storage_installations",
        "number_of_meters",
        "contractless_cases",
        "generation_power",
        "meter_type",
    ):
        assert _entity(api_data, key).native_value is None
    assert _entity(api_data, "smart_meter", binary=True).is_on is None


def test_explicit_empty_generation_lists_have_zero_totals(
    api_data: list[dict[str, object]],
) -> None:
    """A confirmed empty registration list can safely report zero."""
    _connection(api_data)["opwekinstallaties"] = []
    assert _entity(api_data, "generation_power").native_value == pytest.approx(0.0)
    assert _entity(api_data, "solar_panel_power").native_value == pytest.approx(0.0)
    assert _entity(api_data, "generation_installations").native_value == 0


@pytest.mark.parametrize(
    "value",
    [None, "bad", "2024-01-01", "2024-01-01T00:00:00", "9999-12-31T23:59:59-01:00"],
)
def test_invalid_or_naive_timestamps_are_unknown(
    api_data: list[dict[str, object]], value: object
) -> None:
    """Reject missing timezone information and unrepresentable UTC timestamps."""
    _connection(api_data)["levertTerugVanaf"] = value
    assert _entity(api_data, "feed_in_start_date").state is None


async def test_actual_entity_updates_use_one_listener_and_clean_up(
    hass: HomeAssistant, api_data: list[dict[str, object]]
) -> None:
    """Initialize and update all states without duplicate binary callbacks or payloads."""
    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), name=DOMAIN, config_entry=None
    )
    coordinator.async_set_updated_data(api_data)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="synthetic-account")
    entry.add_to_hass(hass)
    sensors = [LianderSensor(coordinator, item, entry) for item in SENSOR_DESCRIPTIONS]
    binaries = [
        LianderBinarySensor(coordinator, item, entry)
        for item in BINARY_SENSOR_DESCRIPTIONS
    ]
    for entity in [*sensors, *binaries]:
        domain = (
            "binary_sensor" if isinstance(entity, LianderBinarySensor) else "sensor"
        )
        entity.entity_id = f"{domain}.fixture_{entity.entity_description.key}"
    sensor_component = EntityComponent(logging.getLogger(__name__), "sensor", hass)
    binary_component = EntityComponent(
        logging.getLogger(__name__), "binary_sensor", hass
    )
    sensor_component._platforms["sensor"].config_entry = entry
    binary_component._platforms["binary_sensor"].config_entry = entry
    await sensor_component.async_add_entities(sensors)
    await binary_component.async_add_entities(binaries)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.fixture_analog") is None
    assert len(coordinator._listeners) == len(sensors) + len(binaries)
    for key, expected in BINARY_VALUES.items():
        state = hass.states.get(f"binary_sensor.fixture_{key}")
        assert state is not None
        assert state.state == (
            "unknown" if expected is None else "on" if expected else "off"
        )
        assert "Elektra" not in state.attributes

    gprs_entity = next(
        item for item in binaries if item.entity_description.key == "gprs"
    )
    updated = deepcopy(api_data)
    _connection(updated)["meters"][0]["gprs"] = True
    with patch.object(
        gprs_entity, "async_write_ha_state", wraps=gprs_entity.async_write_ha_state
    ) as write_state:
        coordinator.async_set_updated_data(updated)
        await hass.async_block_till_done()
        assert write_state.call_count == 1
    assert hass.states.get("binary_sensor.fixture_gprs").state == "on"
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.fixture_smart_meter").state == "unknown"
    for entity in sensors:
        await sensor_component.async_remove_entity(entity.entity_id)
    for entity in binaries:
        await binary_component.async_remove_entity(entity.entity_id)
    assert not coordinator._listeners


@pytest.mark.parametrize("operation", ["login", "data"])
async def test_coordinator_debug_logs_do_not_expose_payloads(
    api_data: list[dict[str, object]], caplog: pytest.LogCaptureFixture, operation: str
) -> None:
    """Keep even synthetic credentials, identifiers, and addresses out of debug logs."""
    coordinator = object.__new__(LianderDataUpdateCoordinator)
    coordinator._username = "synthetic-user@example.invalid"
    coordinator._password = "synthetic-test-password"
    token = jwt.encode(
        {"exp": (datetime.now(UTC) + timedelta(hours=1)).timestamp()},
        "synthetic-test-signing-key-32-characters",
        algorithm="HS256",
    )
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={"jwt": token} if operation == "login" else api_data
    )
    coordinator._session = MagicMock()
    coordinator._session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    coordinator._session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    coordinator.get_valid_token = AsyncMock(return_value=token)
    with caplog.at_level(
        logging.DEBUG, logger="custom_components.mijn_liander.coordinator"
    ):
        if operation == "login":
            await coordinator._async_renew_token()
        else:
            assert await coordinator._async_update_data() is api_data
    for private_value in (
        coordinator._username,
        coordinator._password,
        token,
        "Voorbeeldstraat",
        "TEST-ELECTRIC-001",
        "000000000000000001",
    ):
        assert private_value not in caplog.text


def test_missing_supported_flags_are_unknown(api_data: list[dict[str, object]]) -> None:
    """Keep missing supported connection and meter flags unknown."""
    connection = _connection(api_data)
    del connection["toestemmingVoorUitlezen"]
    del connection["meters"][0]["gprs"]
    assert _entity(api_data, "permission_to_read_data", binary=True).is_on is None
    assert _entity(api_data, "gprs", binary=True).is_on is None
