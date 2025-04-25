# sensor.py
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, Union

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import UNDEFINED, EntityCategory, UndefinedType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMPONENT_TITLE,
    DOMAIN,
    MANUFACTURER,
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_USER,
)
from .coordinator import LianderDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class LianderSensorEntityDescription(SensorEntityDescription):
    """Class to describe a sensor entity with inactive icon support."""
    key: str
    service_name: Union[str, None] = SERVICE_NAME_ELEKTRA
    device_class: SensorDeviceClass | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    force_update: bool = False
    icon: str | None = None
    icon_inactive: str | None = None
    name: str | UndefinedType | None = UNDEFINED
    translation_key: str | None = None
    translation_placeholders: Mapping[str, str] | None = None
    unit_of_measurement: str | None = None
    last_reset: datetime | None = None
    native_unit_of_measurement: str | None = None
    options: list[str] | None = None
    state_class: SensorStateClass | str | None = None
    suggested_display_precision: int | None = None
    suggested_unit_of_measurement: str | None = None


SENSOR_DESCRIPTIONS: list[LianderSensorEntityDescription] = [
    LianderSensorEntityDescription(
        key="address",
        name="Address",
        translation_key="address",
        icon="mdi:home",
        service_name=SERVICE_NAME_USER,
    ),
    LianderSensorEntityDescription(
        key="electricity_ean",
        name="Electricity EAN",
        translation_key="electricity_ean",
        icon="mdi:flash-outline",
    ),
    LianderSensorEntityDescription(
        key="connection_capacity",
        name="Connection Capacity",
        translation_key="connection_capacity",
        icon="mdi:power-socket",
    ),
    LianderSensorEntityDescription(
        key="status",
        name="Status",
        translation_key="status",
        icon="mdi:check-circle",
        icon_inactive="mdi:cancel",
    ),
    LianderSensorEntityDescription(
        key="network_costs",
        name="Network Costs",
        translation_key="network_costs",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
    ),
    LianderSensorEntityDescription(
        key="maximum_power",
        name="Maximum Power",
        translation_key="maximum_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        icon="mdi:flash-triangle-outline",
    ),
    LianderSensorEntityDescription(
        key="number_of_meters",
        name="Number of Meters",
        translation_key="number_of_meters",
        icon="mdi:counter",
    ),
    LianderSensorEntityDescription(
        key="meter_number",
        name="Meter Number",
        translation_key="meter_number",
        icon="mdi:numeric",
    ),
    LianderSensorEntityDescription(
        key="number_of_registers",
        name="Number of Registers",
        translation_key="number_of_registers",
        icon="mdi:counter",
    ),
    LianderSensorEntityDescription(
        key="number_of_phases",
        name="Number of Phases",
        translation_key="number_of_phases",
        icon="mdi:trending-up",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Mijn Liander sensor platform from a config entry."""
    coordinator: LianderDataUpdateCoordinator = hass.data[DOMAIN].get(
        config_entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Coordinator not found for entry_id: %s",
                      config_entry.entry_id)
        return

    sensors = [
        LianderSensor(coordinator, description, config_entry)
        for description in SENSOR_DESCRIPTIONS
    ]

    # Add entities
    async_add_entities(sensors, True)


@dataclass
class SensorAttributes:
    """Class for storing sensor attributes."""
    name: str
    device_class: Optional[SensorDeviceClass] = None
    state_class: Optional[SensorStateClass] = None
    native_unit_of_measurement: Optional[str] = None
    icon: Optional[str] = None
    icon_inactive: Optional[str] = None
    translation_key: Optional[str] = None


class LianderSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Liander sensor."""

    def __init__(
        self,
        coordinator: LianderDataUpdateCoordinator,
        description: LianderSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: LianderSensorEntityDescription = description
        self.entry = entry
        self._attr_unique_id = f"{entry.unique_id}.{description.key}"
        self._attr_name = description.name or "Unnamed Sensor"
        self._attr_translation_key = description.translation_key
        self._attributes = SensorAttributes(
            name=self._attr_name,
            device_class=description.device_class or None,
            state_class=description.state_class or None,
            native_unit_of_measurement=description.native_unit_of_measurement or None,
            icon=description.icon or None,
            icon_inactive=description.icon_inactive or None,
            translation_key=description.translation_key or None
        )

    @property
    def name(self) -> str:
        """Return the translated name of the sensor."""
        return self._attr_name or "Unnamed Sensor"

    @property
    def device_class(self) -> Optional[SensorDeviceClass]:
        return self._attributes.device_class

    @property
    def state_class(self) -> Optional[SensorStateClass]:
        return self._attributes.state_class

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        return self._attributes.native_unit_of_measurement

    @property
    def icon(self) -> Optional[str]:
        if self._attributes.icon_inactive and self.is_inactive():
            return self._attributes.icon_inactive
        return self._attributes.icon

    def is_inactive(self) -> bool:
        """Determine if the sensor is active."""
        return self.native_value not in ["In bedrijf", "Active"]

    @property
    def translation_key(self) -> Optional[str]:
        return self._attributes.translation_key

    @property
    def device_info(self) -> dict:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id, None)},
            "name": "Mijn Liander - Elektra Aansluiting",
            "translation_key": f"{COMPONENT_TITLE} - {SERVICE_NAME_ELEKTRA}",
            "manufacturer": MANUFACTURER,
            "entry_type": DeviceEntryType.SERVICE,
            "model": "Elektra",
            "via_device": (DOMAIN, "API"),
        }

    @property
    def native_value(self) -> Optional[Union[str, int]]:
        """Return the state of the sensor."""
        data = self.coordinator.data
        value = None

        if data:
            for account in data:
                address = account.get('adres', {})
                if address and isinstance(address, dict):
                    if self.entity_description.key == "address":
                        street = address.get('straat', '')
                        house_number = address.get('huisnummer', '')
                        addition = address.get('toevoeging', '')
                        postal_code = address.get('postcode', '')
                        city = address.get('plaats', '')

                        # Formatting the address
                        value = f"{street} {house_number}{
                            addition} {postal_code} {city}".strip()
                        return value

                elektra_connections = account.get(
                    'aansluitingen', {}).get('elektra', [])
                if elektra_connections:
                    elektra = elektra_connections[0]
                    if self.entity_description.key == "electricity_ean":
                        value = elektra.get("ean")
                    elif self.entity_description.key == "connection_capacity":
                        value = elektra.get("aansluitwaarde")
                    elif self.entity_description.key == "status":
                        value = elektra.get("status")
                    elif self.entity_description.key == "network_costs":
                        value = elektra.get("netwerkkosten")
                    elif self.entity_description.key == "maximum_power":
                        value = elektra.get("maximaalVermogen")

                    meters = elektra.get('meters', [])
                    if meters:
                        if self.entity_description.key == "number_of_meters":
                            value = len(meters)
                        meter = meters[0]
                        if self.entity_description.key == "meter_number":
                            value = meter.get("meternummer")
                        elif self.entity_description.key == "number_of_registers":
                            value = meter.get("aantalTelwerken")
                        elif self.entity_description.key == "number_of_phases":
                            value = meter.get("aantalFasen")

                    if value is not None:
                        _LOGGER.debug("Sensor %s: %s",
                                      self._attr_unique_id, value)
                        return value
                    else:
                        _LOGGER.debug("Sensor %s: No data found for key %s",
                                      self._attr_unique_id, self.entity_description.key)

        return None
