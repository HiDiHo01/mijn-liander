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
    VERSION,
)
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

    coordinator: LianderDataUpdateCoordinator = hass.data[DOMAIN].get(config_entry.entry_id)

    binary_sensors = [
        LianderBinarySensor(coordinator, description, config_entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
        # if coordinator.api.auth.is_authenticated
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
        name="Status",
        translation_key="status",
        icon="mdi:check-circle",
        icon_inactive="mdi:cancel",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="contract_active",
        name="Contract Active",
        translation_key="contract_active",
        icon="mdi:check",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="permission_to_read_data",
        name="Permission to Read Data",
        translation_key="permission_to_read_data",
        icon="mdi:eye-check-outline",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="smart_meter",
        name="Smart Meter",
        translation_key="smart_meter",
        icon="mdi:meter-electric",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="gprs",
        name="GPRS Connection",
        translation_key="gprs",
        icon="mdi:signal",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="analog",
        name="Analog",
        translation_key="analog",
        icon="mdi:waveform",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_backfeeding",
        name="Suitable for Backfeed",
        translation_key="suitable_for_backfeeding",
        icon="mdi:transmission-tower",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_dual_tariff",
        name="Suitable for Dual Tariff",
        translation_key="suitable_for_dual_tariff",
        icon="mdi:cash-multiple",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="backfeeding_energy",
        name="Backfeeding Energy",
        translation_key="backfeeding_energy",
        icon="mdi:transmission-tower-import",
        service_name="Elektra"
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
            via_device=(DOMAIN, "API"),
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

        for account in data:
            if not isinstance(account, dict):
                continue

            elektra_connections = account.get(
                'aansluitingen', {}).get('elektra', [])
            if not elektra_connections:
                continue

            elektra = elektra_connections[0]
            meters = elektra.get('meters', [])

            key = self.entity_description.key
            if key == "contract_active":
                return elektra.get("contract", False)
            elif key == "permission_to_read_data":
                return elektra.get("toestemmingVoorUitlezen", False)
            elif key == "smart_meter" and meters:
                return meters[0].get("slimmeMeter", False)
            elif key == "gprs" and meters:
                return meters[0].get("gprs", False)
            elif key == "analog" and meters:
                return meters[0].get("analoog", False)
            elif key == "suitable_for_backfeeding" and meters:
                return meters[0].get("geschiktVoorTerugleveren", False)
            elif key == "suitable_for_dual_tariff" and meters:
                return meters[0].get("geschiktVoorDubbeltarief", False)
            elif key == "backfeeding_energy":
                return elektra.get("levertTerug", False)
            elif key == "status":
                return elektra.get("status", "") == "In bedrijf"
            _LOGGER.warning(
                "Unknown binary sensor key: %s", key)
            return False
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
