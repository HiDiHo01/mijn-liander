"""Expose Mijn Liander account, connection, and installation sensors."""

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    EntityCategory,
    UnitOfPower,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMPONENT_TITLE,
    CONFIG_URL,
    DOMAIN,
    MANUFACTURER,
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_GAS,
    SERVICE_NAME_USER,
    VERSION,
)
from .coordinator import LianderDataUpdateCoordinator
from .data import get_connection, get_first_meter, get_mapping_list
from .gas import filter_entity_descriptions

_LOGGER = logging.getLogger(__name__)

ADDRESS_FIELDS: dict[str, str] = {
    "postal_code": "postcode",
    "street": "straat",
    "house_number": "huisnummer",
    "house_number_addition": "toevoeging",
    "city": "plaats",
}
GENERATION_FIELDS = (
    "terugleverdatum",
    "primaireBron",
    "vermogenOpwekinstallatie",
    "merkOmvormer",
    "typeOmvormer",
    "ean",
    "vermogenZonnepanelen",
    "maxVermogenEenheid",
    "maxVermogenEenheidZonnepanelen",
    "eanOpwekinstallatie",
    "registratiedatum",
)


def _scalar_value(value: object) -> str | int | float | None:
    """Reject containers, booleans, and non-finite values at scalar boundaries."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _generation_details(
    installation: dict[str, object],
) -> dict[str, str | int | float]:
    """Select documented scalar installation details without copying unknown fields."""
    details: dict[str, str | int | float] = {}
    for field in GENERATION_FIELDS:
        value = _scalar_value(installation.get(field))
        if value is not None:
            details[field] = value
    return details


def _get_address_data(data: object) -> dict[str, object] | None:
    """Return the first account address used by all user address sensors."""
    if not isinstance(data, list):
        return None
    for account in data:
        if isinstance(account, dict) and isinstance(
            address := account.get("adres"), dict
        ):
            return address
    return None


def _parse_numeric_value(value: object) -> float | None:
    """Convert a finite API number or decimal-comma string to a float."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, str) and "_" in value:
        return None
    try:
        number = float(value.replace(",", ".") if isinstance(value, str) else value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _parse_timestamp(value: object) -> datetime | None:
    """Parse an API timestamp only when it includes an explicit timezone."""
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            return None
        return timestamp.astimezone(UTC)
    except (ValueError, OverflowError):
        return None


def _sum_generation_power(
    connection: dict[str, object], value_field: str, unit_field: str
) -> float | None:
    """Sum complete, finite kW installation ratings without partial totals."""
    installations = get_mapping_list(connection.get("opwekinstallaties"))
    if installations is None:
        return None
    total = 0.0
    for installation in installations:
        unit = installation.get(unit_field)
        power = _parse_numeric_value(installation.get(value_field))
        if not isinstance(unit, str) or unit.upper() != "KW" or power is None:
            return None
        if power < 0:
            return None
        total += power
    return total if math.isfinite(total) else None


@dataclass(frozen=True, kw_only=True)
class LianderSensorEntityDescription(SensorEntityDescription):
    """Class to describe a sensor entity with inactive icon support."""
    key: str
    service_name: str | None = SERVICE_NAME_ELEKTRA
    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    force_update: bool = False
    icon: str | None = None
    icon_inactive: str | None = None
    name: str | UndefinedType | None = UNDEFINED
    translation_key: str | None = None
    last_reset: datetime | None = None
    native_unit_of_measurement: str | None = None
    options: list[str] | None = None
    state_class: SensorStateClass | None = None
    suggested_display_precision: int | None = None
    suggested_unit_of_measurement: str | None = None


SENSOR_DESCRIPTIONS: list[LianderSensorEntityDescription] = [
    LianderSensorEntityDescription(
        key="address",
        translation_key="address",
        icon="mdi:home",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="postal_code",
        translation_key="postal_code",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="street",
        translation_key="street",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="house_number",
        translation_key="house_number",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="house_number_addition",
        translation_key="house_number_addition",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="city",
        translation_key="city",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="electricity_ean",
        translation_key="electricity_ean",
        icon="mdi:flash-outline",
    ),
    LianderSensorEntityDescription(
        key="connection_capacity",
        translation_key="connection_capacity",
        icon="mdi:power-socket",
    ),
    LianderSensorEntityDescription(
        key="network_costs",
        translation_key="network_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
    ),
    LianderSensorEntityDescription(
        key="maximum_power",
        translation_key="maximum_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=0,
        icon="mdi:flash-triangle-outline",
    ),
    LianderSensorEntityDescription(
        key="number_of_meters",
        translation_key="number_of_meters",
        icon="mdi:counter",
    ),
    LianderSensorEntityDescription(
        key="meter_number",
        translation_key="meter_number",
        icon="mdi:numeric",
    ),
    LianderSensorEntityDescription(
        key="number_of_registers",
        translation_key="number_of_registers",
        icon="mdi:counter",
    ),
    LianderSensorEntityDescription(
        key="number_of_phases",
        translation_key="number_of_phases",
        icon="mdi:trending-up",
    ),
    LianderSensorEntityDescription(
        key="feed_in_start_date",
        translation_key="feed_in_start_date",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-arrow-right",
    ),
    LianderSensorEntityDescription(
        key="generation_installations",
        translation_key="generation_installations",
        icon="mdi:solar-power-variant",
        icon_inactive="mdi:solar-power-variant-outline",
    ),
    LianderSensorEntityDescription(
        key="storage_installations",
        translation_key="storage_installations",
        icon="mdi:battery",
        icon_inactive="mdi:battery-outline",
    ),
    LianderSensorEntityDescription(
        key="generation_power",
        translation_key="generation_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    LianderSensorEntityDescription(
        key="solar_panel_power",
        translation_key="solar_panel_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    LianderSensorEntityDescription(key="meter_type", translation_key="meter_type"),
    LianderSensorEntityDescription(
        key="contractless_cases", translation_key="contractless_cases"
    ),
    LianderSensorEntityDescription(
        key="gas_ean",
        translation_key="gas_ean",
        icon="mdi:meter-gas",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_connection_capacity",
        translation_key="gas_connection_capacity",
        icon="mdi:pipe",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_network_costs",
        translation_key="gas_network_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_maximum_capacity",
        translation_key="gas_maximum_capacity",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        suggested_display_precision=0,
        icon="mdi:gauge",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_number_of_meters",
        translation_key="gas_number_of_meters",
        icon="mdi:counter",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_meter_number",
        translation_key="gas_meter_number",
        icon="mdi:numeric",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_number_of_registers",
        translation_key="gas_number_of_registers",
        icon="mdi:counter",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_meter_type",
        translation_key="gas_meter_type",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderSensorEntityDescription(
        key="gas_contractless_cases",
        translation_key="gas_contractless_cases",
        service_name=SERVICE_NAME_GAS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Mijn Liander sensor platform from a config entry."""
    await asyncio.sleep(0)
    coordinator: LianderDataUpdateCoordinator = hass.data[DOMAIN].get(
        config_entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Coordinator not found for entry_id: %s",
                      config_entry.entry_id)
        return

    sensors = [
        LianderSensor(coordinator, description, config_entry)
        for description in filter_entity_descriptions(
            SENSOR_DESCRIPTIONS, coordinator.data
        )
    ]

    # Add entities
    async_add_entities(sensors, True)


@dataclass
class SensorAttributes:
    """Class for storing sensor attributes."""
    name: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    icon: str | None = None
    icon_inactive: str | None = None
    translation_key: str | None = None


# class LianderSensor(CoordinatorEntity, SensorEntity):
class LianderSensor(CoordinatorEntity[LianderDataUpdateCoordinator], SensorEntity):
    """Representation of a Liander sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LianderDataUpdateCoordinator,
        description: LianderSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attributes = SensorAttributes(
            name=(description.name if isinstance(description.name, str) else "Unnamed Sensor"),
            device_class=description.device_class or None,
            state_class=description.state_class or None,
            native_unit_of_measurement=description.native_unit_of_measurement or None,
            icon=description.icon or None,
            icon_inactive=description.icon_inactive or None,
            translation_key=description.translation_key or None
        )

        if description.service_name == SERVICE_NAME_ELEKTRA or description.service_name is None:
            device_info_identifiers: set[tuple[str, str]] = {
                (DOMAIN, entry.entry_id)
            }
        else:
            device_info_identifiers: set[tuple[str, str]] = {
                (DOMAIN, f"{entry.entry_id}_{description.service_name}")
            }

        self._attr_device_info = DeviceInfo(
            identifiers=device_info_identifiers,
            name=f"{COMPONENT_TITLE} - {description.service_name}",
            translation_key=f"{COMPONENT_TITLE} - {description.service_name}",
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=CONFIG_URL,
            model=description.service_name,
            sw_version=VERSION,
        )

    @property
    def icon(self) -> str | None:  # type: ignore[override]
        """Return the icon depending on sensor activity."""
        if self._attributes.icon_inactive and self.is_inactive():
            return self._attributes.icon_inactive
        return self._attributes.icon

    @property
    def suggested_display_precision(self) -> int | None:
        """Suggest one decimal when the raw maximum-power value contains a comma."""
        if self.entity_description.key == "maximum_power":
            raw_value = self._get_raw_value()
            if isinstance(raw_value, str) and "," in raw_value:
                return 1
        return self.entity_description.suggested_display_precision

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the stored display default and publish updated coordinator data."""
        if self.entity_description.key == "maximum_power" and self.registry_entry:
            self._update_suggested_precision()
        super()._handle_coordinator_update()

    def is_inactive(self) -> bool:
        """Return whether a known count or status indicates inactivity."""
        value = self.native_value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value <= 0
        if isinstance(value, str) and value.isdecimal():
            return int(value) <= 0
        return value not in ("In bedrijf", "Active")

    def _get_address_value(self, data: object) -> str | None:
        """Get address string from coordinator data."""
        address = _get_address_data(data)
        if address is None:
            return None
        street = address.get("straat", "")
        house_number = address.get("huisnummer", "")
        addition = address.get("toevoeging", "")
        postal_code = address.get("postcode", "")
        city = address.get("plaats", "")
        return f"{street} {house_number}{addition} {postal_code} {city}".strip()

    def _get_address_field_value(self, data: object) -> str | None:
        """Return one textual address field, preserving numeric house numbers."""
        address = _get_address_data(data)
        if address is None:
            return None
        sensor_key = self.entity_description.key
        raw_value = address.get(ADDRESS_FIELDS[sensor_key])
        if isinstance(raw_value, str):
            return raw_value
        if sensor_key == "house_number" and type(raw_value) is int:
            return str(raw_value)
        return None

    def _get_connection_value(
        self, connection: dict[str, object], key: str
    ) -> str | int | float | None:
        """Get sensor value from connection data."""
        connection_fields = {
            "electricity_ean": "ean",
            "connection_capacity": "aansluitwaarde",
            "network_costs": "netwerkkosten",
            "maximum_power": "maximaalVermogen",
            "feed_in_start_date": "levertTerugVanaf",
            "gas_ean": "ean",
            "gas_connection_capacity": "aansluitwaarde",
            "gas_network_costs": "netwerkkosten",
            "gas_maximum_capacity": "maximaleCapaciteit",
        }
        if key in connection_fields:
            return _scalar_value(connection.get(connection_fields[key]))
        collection_fields = {
            "generation_installations": "opwekinstallaties",
            "storage_installations": "opslaginstallaties",
            "contractless_cases": "contractloosCases",
            "gas_contractless_cases": "contractloosCases",
        }
        if key in collection_fields:
            collection = get_mapping_list(connection.get(collection_fields[key]))
            return len(collection) if collection is not None else None
        if key == "generation_power":
            return _sum_generation_power(
                connection, "vermogenOpwekinstallatie", "maxVermogenEenheid"
            )
        if key == "solar_panel_power":
            return _sum_generation_power(
                connection, "vermogenZonnepanelen", "maxVermogenEenheidZonnepanelen"
            )

        meters = get_mapping_list(connection.get("meters"))
        if key in {"number_of_meters", "gas_number_of_meters"}:
            return len(meters) if meters is not None else None
        meter = get_first_meter(connection)
        if meter is None:
            return None

        meter_fields = {
            "meter_number": "meternummer",
            "number_of_registers": "aantalTelwerken",
            "number_of_phases": "aantalFasen",
            "gas_meter_number": "meternummer",
            "gas_number_of_registers": "aantalTelwerken",
            "meter_type": "type",
            "gas_meter_type": "type",
        }
        return _scalar_value(meter.get(meter_fields[key])) if key in meter_fields else None

    def _get_raw_value(self) -> str | int | float | None:
        """Return the unconverted sensor value from coordinator data."""
        data = self.coordinator.data

        if not data:
            _LOGGER.debug("No coordinator data available for sensor %s", self._attr_unique_id)
            return None

        if self.entity_description.key == "address":
            return self._get_address_value(data)
        if self.entity_description.key in ADDRESS_FIELDS:
            return self._get_address_field_value(data)

        connection = get_connection(data, self.entity_description.service_name)
        if connection is None:
            return None

        return self._get_connection_value(connection, self.entity_description.key)

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor state, normalizing numeric API measurements."""
        value = self._get_raw_value()
        if self.entity_description.key == "feed_in_start_date":
            return _parse_timestamp(value)
        if self.entity_description.native_unit_of_measurement is not None:
            number = _parse_numeric_value(value)
            if (
                self.entity_description.key == "gas_maximum_capacity"
                and number is not None
            ):
                return int(number)
            return number
        return value

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Expose allowlisted generation registration details without raw payloads."""
        if self.entity_description.key != "generation_installations":
            return None
        connection = get_connection(self.coordinator.data, SERVICE_NAME_ELEKTRA)
        if connection is None:
            return None
        installations = get_mapping_list(connection.get("opwekinstallaties"))
        if installations is None:
            return None
        details = [_generation_details(installation) for installation in installations]
        return {"installations": details}
