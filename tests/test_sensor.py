"""Verify installation-count icons and their upstream catalog membership."""

import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from custom_components.mijn_liander.sensor import SENSOR_DESCRIPTIONS, LianderSensor


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
