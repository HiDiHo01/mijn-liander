"""
Binary Sensor platform for Mijn Liander.
"""
# binary_sensor.py
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (ATTRIBUTION, COMPONENT_TITLE, CONFIG_URL, DOMAIN,
                    MANUFACTURER, SERVICE_NAME_ELEKTRA, VERSION)
from .coordinator import LianderDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Mijn Liander binary sensor based on a config entry."""
    _LOGGER.debug("Setting up Mijn Liander binary sensor for entry: %s",
                  config_entry.entry_id)

    # Ensure the config entry has a unique ID
    if config_entry.unique_id is None:
        unique_id = str(uuid.uuid4())
        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id)
    else:
        unique_id = config_entry.unique_id

    coordinator: LianderDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    binary_sensors = [
        LianderBinarySensor(coordinator, description, config_entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if not description.authenticated
        or coordinator.api.auth.is_authenticated
    ]

    # async_add_entities(sensors + binary_sensors)
    async_add_entities(binary_sensors, True)


@dataclass
class LianderBinaryEntityDescription:
    """Representation of a Sensor."""
    key: str
    name: str
    device_class: Optional[str] = None
    state_class: Optional[str] = None
    native_unit_of_measurement: Optional[str] = None
    suggested_display_precision: Optional[int] = None
    authenticated: bool = False
    service_name: Union[str, None] = SERVICE_NAME_ELEKTRA
    value_fn: Optional[Callable[[dict], StateType]] = None
    attr_fn: Callable[[dict], dict[str, Union[StateType, list]]] = field(
        default_factory=lambda: {}  # type: ignore
    )
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    translation_key: Optional[str] = None
    icon: Optional[str] = None
    entity_category: Optional[str] = None
    force_update: bool = False

    def __post_init__(self):
        if self.value_fn is None:
            self.value_fn = lambda data: STATE_UNKNOWN
        if self.attr_fn is None:
            self.attr_fn = lambda data: {}

    @property
    def has_entity_name(self) -> bool:
        """Return if the entity has a name."""
        return bool(self.name)

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        return self.native_unit_of_measurement


BINARY_SENSOR_DESCRIPTIONS: list[LianderBinaryEntityDescription] = [
    LianderBinaryEntityDescription(
        key="contract",
        name="Contract Active",
        translation_key="contract",
        icon="mdi:check",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="toestemmingVoorUitlezen",
        name="Permission to Read Data",
        translation_key="toestemmingVoorUitlezen",
        icon="mdi:eye-check-outline",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="slimmeMeter",
        name="Smart Meter",
        translation_key="slimmeMeter",
        icon="mdi:meter-electric",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="geschiktVoorTerugleveren",
        name="Suitable for Backfeed",
        translation_key="geschiktVoorTerugleveren",
        icon="mdi:transmission-tower",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="geschiktVoorDubbeltarief",
        name="Suitable for Dual Tariff",
        translation_key="geschiktVoorDubbeltarief",
        icon="mdi:cash-multiple",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="levertTerug",
        name="Backfeeding Energy",
        translation_key="levertTerug",
        icon="mdi:transmission-tower-import",
        service_name="Elektra"
    ),
]


class LianderBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Liander binary sensor."""

    def __init__(self,
                 coordinator: LianderDataUpdateCoordinator,
                 description: LianderBinaryEntityDescription,
                 entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description: LianderBinaryEntityDescription = description
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_icon = description.icon
        self._attr_is_on = self.is_on

        device_info_identifiers: set[tuple[str, str, Optional[str]]] = (
            {(DOMAIN, entry.entry_id, None)}
            if description.service_name is SERVICE_NAME_ELEKTRA
            else {(DOMAIN, entry.entry_id, description.service_name)}
        )

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

        _LOGGER.debug(
            "LianderBinarySensor initialized with coordinator: %s", coordinator)

    def _update_state(self) -> None:
        """Update the state of the sensor."""
        # self._attr_is_on = self.entity_description.value_fn(
        #     self.coordinator.data)
        self._attr_is_on = self.is_on
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        data = self.coordinator.data
        if not data:
            return False

        for account in data:
            elektra_connections = account.get(
                'aansluitingen', {}).get('elektra', [])
            if elektra_connections:
                elektra = elektra_connections[0]
                meters = elektra.get('meters', [])

                key = self.entity_description.key
                if key == "contract":
                    return elektra.get("contract", False)
                elif key == "toestemmingVoorUitlezen":
                    return elektra.get("toestemmingVoorUitlezen", False)
                elif key == "slimmeMeter" and meters:
                    return meters[0].get("slimmeMeter", False)
                elif key == "geschiktVoorTerugleveren" and meters:
                    return meters[0].get("geschiktVoorTerugleveren", False)
                elif key == "geschiktVoorDubbeltarief" and meters:
                    return meters[0].get("geschiktVoorDubbeltarief", False)
                elif key == "levertTerug":
                    return elektra.get("levertTerug", False)

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Union[str, dict[str, Any], list[Any]]]:
        """Return the state attributes."""
        data = self.coordinator.data
        attributes: dict[str, Union[str, dict[str, Any], list[Any]]] = {
            "attribution": ATTRIBUTION,
            # Flattening the list of 'elektra' across all accounts
            "Elektra": [
                elektra
                for account in data
                for elektra in account.get('aansluitingen', {}).get('elektra', [])
            ] if data else []
        }
        # _LOGGER.debug("Extra state attributes set: %s", attributes)
        return attributes

    async def old_async_added_to_hass(self) -> None:
        """When entity is added to hass during the setup and initialization."""
        _LOGGER.debug("Entity %s added to hass", self._attr_name)
        # await super().async_added_to_hass()

        # Ensure the coordinator is not None and has the async_add_listener method
        if self.coordinator and hasattr(self.coordinator, 'async_add_listener'):
            self.async_on_remove(
                self.coordinator.async_add_listener(self._update_state)
            )
        else:
            _LOGGER.error(
                "Coordinator is None or does not have async_add_listener method.")

    async def async_update(self) -> None:
        """Update the entity state."""
        if self.coordinator and hasattr(self.coordinator, 'async_request_refresh'):
            # Forcing a data refresh request from the coordinator manually (not in use)
            # Uncomment to force a refresh if needed
            # await self.coordinator.async_request_refresh()
            pass
        else:
            _LOGGER.error(
                "Coordinator is None or does not have async_request_refresh method.")
            # Forcing a data refresh request from the coordinator manually (not in use)
            # Uncomment to force a refresh if needed
            # await self.coordinator.async_request_refresh()
            pass
