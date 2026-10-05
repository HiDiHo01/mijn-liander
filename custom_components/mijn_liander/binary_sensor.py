"""
Binary Sensor platform for Mijn Liander.
"""
# binary_sensor.py
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Union

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    COMPONENT_TITLE,
    CONFIG_URL,
    DOMAIN,
    MANUFACTURER,
    SERVICE_NAME_ELEKTRA,
    SERVICE_NAME_GAS,
    VERSION,
)
from .coordinator import LianderDataUpdateCoordinator
from .gas import filter_entity_descriptions

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

    coordinator: LianderDataUpdateCoordinator = hass.data[DOMAIN].get(config_entry.entry_id)

    binary_sensors = [
        LianderBinarySensor(coordinator, description, config_entry)
        for description in filter_entity_descriptions(
            BINARY_SENSOR_DESCRIPTIONS, coordinator.data
        )
    ]

    async_add_entities(binary_sensors, True)


@dataclass(frozen=True, kw_only=True)
class LianderBinaryEntityDescription(BinarySensorEntityDescription):
    """Representation of a Sensor."""
    key: str
    name: Optional[str] = None
    device_class: Optional[BinarySensorDeviceClass] = None
    state_class: Optional[str] = None
    native_unit_of_measurement: Optional[str] = None
    suggested_display_precision: Optional[int] = None
    # authenticated: bool = False
    service_name: Union[str, None] = SERVICE_NAME_ELEKTRA
    value_fn: Optional[Callable[[dict], StateType]] = None
    attr_fn: Callable[[dict], dict[str, Union[StateType, list[object]]]] = field(
        default_factory=lambda: {}  # type: ignore
    )
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    translation_key: Optional[str] = None
    icon: Optional[str] = None
    icon_inactive: Optional[str] = None
    entity_category: Optional[EntityCategory] = None
    force_update: bool = False
    is_on_fn: Callable[[dict], bool] | None = None
    translation_placeholders: dict[str, str] | None = None

    def __post_init__(self):
        if self.value_fn is None:
            object.__setattr__(self, "value_fn", lambda data: STATE_UNKNOWN)
        if self.attr_fn is None:
            object.__setattr__(self, "attr_fn", lambda data: {})
        if self.translation_placeholders is None:
            object.__setattr__(self, "translation_placeholders", {})


BINARY_SENSOR_DESCRIPTIONS: list[LianderBinaryEntityDescription] = [
    LianderBinaryEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:check-circle",
        icon_inactive="mdi:cancel",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="contract_active",
        translation_key="contract_active",
        icon="mdi:check",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="permission_to_read_data",
        translation_key="permission_to_read_data",
        icon="mdi:eye-check-outline",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="smart_meter",
        translation_key="smart_meter",
        icon="mdi:meter-electric",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="gprs",
        translation_key="gprs",
        icon="mdi:signal",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="analog",
        translation_key="analog",
        icon="mdi:waveform",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_backfeeding",
        translation_key="suitable_for_backfeeding",
        icon="mdi:transmission-tower",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_dual_tariff",
        translation_key="suitable_for_dual_tariff",
        icon="mdi:cash-multiple",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="backfeeding_energy",
        translation_key="backfeeding_energy",
        icon="mdi:transmission-tower-import",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="meter_fault_check_allowed",
        translation_key="meter_fault_check_allowed",
        icon="mdi:meter-electric-outline",
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="smart_meter_request_allowed",
        translation_key="smart_meter_request_allowed",
        icon="mdi:meter-electric",
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="net_metering",
        translation_key="net_metering",
        icon="mdi:solar-power",
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="gas_status",
        translation_key="gas_status",
        icon="mdi:check-circle",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_contract_active",
        translation_key="gas_contract_active",
        icon="mdi:check",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_permission_to_read_data",
        translation_key="gas_permission_to_read_data",
        icon="mdi:eye-check-outline",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_meter_fault_check_allowed",
        translation_key="gas_meter_fault_check_allowed",
        icon="mdi:meter-gas",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_smart_meter",
        translation_key="gas_smart_meter",
        icon="mdi:meter-gas",
        service_name=SERVICE_NAME_GAS,
    ),
]


class LianderBinarySensor(
    CoordinatorEntity[LianderDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Binary sensor for Mijn Liander data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LianderDataUpdateCoordinator,
        description: LianderBinaryEntityDescription,
        entry: ConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        # self.entity_description = description
        self.entity_description: LianderBinaryEntityDescription = description  # type: ignore[override]
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        # DeviceInfo.identifiers expects set[tuple[str, str]] so ensure we provide
        # a pair. Include the service name in the second element for service
        # devices to keep identifiers unique per service.
        if description.service_name == SERVICE_NAME_ELEKTRA:
            device_info_identifiers: set[tuple[str, str]] = {(DOMAIN, entry.entry_id)}
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

        _LOGGER.debug(
            "LianderBinarySensor initialized with coordinator: %s", coordinator)

    @property
    def icon(self) -> str | None:  # type: ignore[override]
        """Return the icon depending on sensor activity."""
        icon_inactive = getattr(self.entity_description, "icon_inactive", None)
        if icon_inactive is not None and self.is_inactive():
            return icon_inactive
        return self.entity_description.icon

    def _update_state(self) -> None:
        """Update the state of the sensor."""
        self._attr_is_on = self._get_is_on()
        self.async_write_ha_state()

    def is_inactive(self) -> bool:
        """Determine if the sensor is active."""
        return not getattr(self, "_attr_is_on", False)

    def _get_is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        data = self.coordinator.data
        if not data:
            return False

        connection_type = (
            "gas"
            if self.entity_description.service_name == SERVICE_NAME_GAS
            else "elektra"
        )
        connection = next(
            (
                item
                for account in data
                if isinstance(account, dict)
                for item in (account.get("aansluitingen", {}).get(connection_type, []) or [])
                if isinstance(item, dict)
            ),
            None,
        )
        if connection is None:
            return False

        key = self.entity_description.key.removeprefix("gas_")
        connection_fields = {
            "contract_active": "contract",
            "permission_to_read_data": "toestemmingVoorUitlezen",
            "meter_fault_check_allowed": "meterstoringscheckToegestaan",
            "smart_meter_request_allowed": "nieuweSlimmeMeterAanvragenToegestaan",
            "backfeeding_energy": "levertTerug",
        }
        if key == "status":
            return connection.get("status") == "In bedrijf"
        if key in connection_fields:
            return bool(connection.get(connection_fields[key], False))
        if key == "net_metering":
            meters = connection.get("meters", []) or []
            return bool(meters and meters[0].get("salderingsregeling", False))

        meter_fields = {
            "smart_meter": "slimmeMeter",
            "gprs": "gprs",
            "analog": "analoog",
            "suitable_for_backfeeding": "geschiktVoorTerugleveren",
            "suitable_for_dual_tariff": "geschiktVoorDubbeltarief",
        }
        if key in meter_fields:
            meters = connection.get("meters", []) or []
            return bool(meters and meters[0].get(meter_fields[key], False))

        _LOGGER.warning("Unknown binary sensor key: %s", self.entity_description.key)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Union[str, list[object], bool, None]]:  # type: ignore[override]
        """Return the state attributes."""
        data = self.coordinator.data
        attributes: dict[str, Union[str, list[object], bool, None]] = {
            "attribution": ATTRIBUTION,
            "state": self.state,
            "assumed_state": (self.assumed_state() if callable(self.assumed_state) else self.assumed_state),
            # Flattening the list of 'elektra' across all accounts
            "Elektra": [
                elektra
                for account in data
                if isinstance(account, dict)
                for elektra in account.get('aansluitingen', {}).get('elektra', [])
            ]
        }
        # _LOGGER.debug("Extra state attributes set: %s", attributes)
        return attributes

    async def async_added_to_hass(self) -> None:
        """Register callback after entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._update_state)
        )

    async def async_update(self) -> None:
        """Trigger a manual update via the coordinator.
        This will never be called unless:
        Home Assistant requests it via entity.async_update(), which it normally doesn’t for coordinator-based entities.
        You or another integration explicitly call async_update().
        This is useful for testing or if you want to force an update manually.
        Note: This method is not typically used in coordinator-based entities.
        """
        # Forcing a data refresh request from the coordinator manually (not in use)
        await self.coordinator.async_request_refresh()
