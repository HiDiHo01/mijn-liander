"""Verify Mijn Liander sensor values and installation-icon behavior."""

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from homeassistant.helpers.entity_platform import PlatformData

from custom_components.mijn_liander.const import DOMAIN
from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS, LianderSensor

NUMERIC_SENSOR_FIELDS = (
    pytest.param("maximum_power", "elektra", "maximaalVermogen", id="maximum-power"),
    pytest.param("network_costs", "elektra", "netwerkkosten", id="electricity-costs"),
    pytest.param("gas_network_costs", "gas", "netwerkkosten", id="gas-costs"),
)


@pytest.fixture(name="mdi_catalog_names")
def mdi_catalog_fixture() -> set[str]:
    """Load canonical icon names from the pinned upstream MDI snapshot."""
    catalog_path = Path(__file__).parent / "fixtures" / "mdi_catalog.json"
    return set(json.loads(catalog_path.read_text(encoding="utf-8"))["names"])


def _make_sensor(
    sensor_key: str, coordinator_data: list[dict[str, object]] | None
) -> LianderSensor:
    """Build an entity with synthetic coordinator data and a stable entry identity."""
    description = next(item for item in SENSOR_DESCRIPTIONS if item.key == sensor_key)
    coordinator = MagicMock(data=coordinator_data)
    entry = MagicMock(unique_id="test-account", entry_id="test-entry-id")
    return LianderSensor(coordinator, description, entry)


def _make_connection_sensor(
    sensor_key: str, connection_type: str, data_key: str, raw_value: object
) -> LianderSensor:
    """Build a sensor from a synthetic active connection and one API field."""
    sensor = _make_sensor(
        sensor_key,
        [
            {
                "aansluitingen": {
                    connection_type: [{"contract": True, data_key: raw_value}]
                }
            }
        ],
    )
    sensor.platform_data = PlatformData(
        MagicMock(), domain="sensor", platform_name=DOMAIN
    )
    return sensor


@pytest.mark.parametrize(
    ("sensor_key", "connection_type", "data_key"), NUMERIC_SENSOR_FIELDS
)
@pytest.mark.parametrize(
    ("raw_value", "expected_value"),
    [
        ("8,1", 8.1),
        (" 8,1 ", 8.1),
        ("8.1", 8.1),
        ("8", 8.0),
        (8, 8.0),
        (8.1, 8.1),
        (0, 0.0),
        ("0,0", 0.0),
        ("-2,5", -2.5),
    ],
)
def test_numeric_api_values_are_floats(
    sensor_key: str,
    connection_type: str,
    data_key: str,
    raw_value: object,
    expected_value: float,
) -> None:
    """Convert decimal-comma API values before Home Assistant validates the state."""
    sensor = _make_connection_sensor(sensor_key, connection_type, data_key, raw_value)

    assert sensor.state == pytest.approx(expected_value)
    assert isinstance(sensor.native_value, float)
    assert sensor.native_value == pytest.approx(expected_value)


@pytest.mark.parametrize(
    ("sensor_key", "connection_type", "data_key"), NUMERIC_SENSOR_FIELDS
)
@pytest.mark.parametrize(
    "raw_value",
    [
        None,
        "",
        "unknown",
        "8,1 kW",
        "1.234,56",
        "NaN",
        "Infinity",
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        [],
        {},
        pytest.param(10**1000, id="overflowing-integer"),
    ],
)
def test_invalid_numeric_api_values_are_unknown(
    sensor_key: str, connection_type: str, data_key: str, raw_value: object
) -> None:
    """Reject invalid measurements without inventing zero or raising a state error."""
    sensor = _make_connection_sensor(sensor_key, connection_type, data_key, raw_value)

    assert sensor.native_value is None
    assert sensor.state is None


@pytest.mark.parametrize(
    ("sensor_key", "connection_type", "data_key", "raw_value"),
    [
        ("electricity_ean", "elektra", "ean", "001234567890123456"),
        ("gas_ean", "gas", "ean", "001234567890123456"),
        ("connection_capacity", "elektra", "aansluitwaarde", "3 x 25 A"),
        ("gas_maximum_capacity", "gas", "maximaleCapaciteit", "8,1"),
    ],
)
def test_numeric_conversion_preserves_text_fields(
    sensor_key: str, connection_type: str, data_key: str, raw_value: str
) -> None:
    """Keep identifiers and text-only connection properties exactly as supplied."""
    sensor = _make_connection_sensor(sensor_key, connection_type, data_key, raw_value)

    assert sensor.native_value == raw_value


@pytest.mark.parametrize(
    ("sensor_key", "data_key", "active_icon", "inactive_icon"),
    [
        (
            "generation_installations",
            "opwekinstallaties",
            "mdi:solar-power-variant",
            "mdi:solar-power-variant-outline",
        ),
        (
            "storage_installations",
            "opslaginstallaties",
            "mdi:battery",
            "mdi:battery-outline",
        ),
    ],
)
@pytest.mark.parametrize("installation_count", [0, 1, 2])
def test_installation_count_icon_resolution(
    sensor_key: str,
    data_key: str,
    active_icon: str,
    inactive_icon: str,
    installation_count: int,
    mdi_catalog_names: set[str],
) -> None:
    """Use outlined icons only for zero installations and validate the chosen icon."""
    sensor = _make_sensor(
        sensor_key,
        [
            {
                "aansluitingen": {
                    "elektra": [{data_key: [{} for _ in range(installation_count)]}]
                }
            }
        ],
    )

    assert sensor.native_value == installation_count
    assert sensor.is_inactive() is (installation_count == 0)
    assert sensor.icon == (inactive_icon if installation_count == 0 else active_icon)
    assert sensor.icon.removeprefix("mdi:") in mdi_catalog_names


@pytest.mark.parametrize(
    ("sensor_key", "expected_icon"),
    [
        ("generation_installations", "mdi:solar-power-variant"),
        ("storage_installations", "mdi:battery"),
    ],
)
@pytest.mark.parametrize(
    "coordinator_data",
    [
        None,
        [],
        [{"aansluitingen": {"elektra": []}}],
        [{"aansluitingen": {"gas": [{}]}}],
    ],
    ids=["missing-data", "empty-data", "no-electricity", "gas-only"],
)
def test_unknown_installation_counts_keep_default_icon(
    sensor_key: str,
    expected_icon: str,
    coordinator_data: list[dict[str, object]] | None,
    mdi_catalog_names: set[str],
) -> None:
    """Missing data or electricity connections must not imply zero installations."""
    sensor = _make_sensor(sensor_key, coordinator_data)

    assert sensor.native_value is None
    assert sensor.is_inactive() is False
    assert sensor.icon == expected_icon
    assert sensor.icon.removeprefix("mdi:") in mdi_catalog_names


@pytest.mark.parametrize(
    ("native_value", "expected_inactive"),
    [
        (-1, True),
        (0, True),
        (1, False),
        ("0", True),
        ("1", False),
        ("In bedrijf", False),
        ("Active", False),
        ("Inactive", True),
        (None, False),
    ],
)
def test_activity_distinguishes_counts_statuses_and_unknown(
    native_value: str | int | None, expected_inactive: bool
) -> None:
    """Preserve text statuses and distinguish known counts from unknown values."""
    sensor = _make_sensor("generation_installations", None)

    with patch.object(
        LianderSensor,
        "native_value",
        new_callable=PropertyMock,
        return_value=native_value,
    ):
        assert sensor.is_inactive() is expected_inactive
