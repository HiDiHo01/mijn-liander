"""
Binary Sensor platform for Mijn Liander.
"""
# binary_sensor.py
import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, callback
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
from .data import get_connection, get_first_meter
from .gas import filter_entity_descriptions

_LOGGER = logging.getLogger(__name__)

ICON_CHECK_CIRCLE = "mdi:check-circle"
ICON_METER_ELECTRIC = "mdi:meter-electric"
ICON_METER_ELECTRIC_OUTLINE = "mdi:meter-electric-outline"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Mijn Liander binary sensor based on a config entry."""
    await asyncio.sleep(0)
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
    name: str | None = None
    device_class: BinarySensorDeviceClass | None = None
    state_class: str | None = None
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    service_name: str | None = SERVICE_NAME_ELEKTRA
    value_fn: Callable[[dict], StateType] | None = None
    attr_fn: Callable[[dict], dict[str, StateType | list[object]]] = field(
        default_factory=dict  # type: ignore
    )
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True
    translation_key: str | None = None
    icon: str | None = None
    icon_inactive: str | None = None
    entity_category: EntityCategory | None = None
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
        icon=ICON_CHECK_CIRCLE,
        icon_inactive="mdi:cancel",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="contract_active",
        translation_key="contract_active",
        icon=ICON_CHECK_CIRCLE,
        icon_inactive="mdi:close-circle",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="permission_to_read_data",
        translation_key="permission_to_read_data",
        icon="mdi:eye-check-outline",
        icon_inactive="mdi:eye-off-outline",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="smart_meter",
        translation_key="smart_meter",
        icon=ICON_METER_ELECTRIC,
        icon_inactive=ICON_METER_ELECTRIC_OUTLINE,
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="gprs",
        translation_key="gprs",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:signal",
        icon_inactive="mdi:signal-off",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="analog",
        translation_key="analog",
        icon="mdi:waveform",
        icon_inactive="mdi:sine-wave",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_backfeeding",
        translation_key="suitable_for_backfeeding",
        icon="mdi:transmission-tower",
        icon_inactive="mdi:transmission-tower-off",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="suitable_for_dual_tariff",
        translation_key="suitable_for_dual_tariff",
        icon="mdi:cash-multiple",
        icon_inactive="mdi:cash-off",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="backfeeding_energy",
        translation_key="backfeeding_energy",
        icon="mdi:transmission-tower-import",
        icon_inactive="mdi:transmission-tower-off",
        service_name="Elektra"
    ),
    LianderBinaryEntityDescription(
        key="meter_fault_check_allowed",
        translation_key="meter_fault_check_allowed",
        icon=ICON_METER_ELECTRIC,
        icon_inactive=ICON_METER_ELECTRIC_OUTLINE,
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="smart_meter_request_allowed",
        translation_key="smart_meter_request_allowed",
        icon=ICON_METER_ELECTRIC,
        icon_inactive=ICON_METER_ELECTRIC_OUTLINE,
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="net_metering",
        translation_key="net_metering",
        icon="mdi:solar-power",
        icon_inactive="mdi:solar-power-variant-outline",
        service_name=SERVICE_NAME_ELEKTRA,
    ),
    LianderBinaryEntityDescription(
        key="gas_status",
        translation_key="gas_status",
        icon=ICON_CHECK_CIRCLE,
        icon_inactive="mdi:cancel",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_contract_active",
        translation_key="gas_contract_active",
        icon=ICON_CHECK_CIRCLE,
        icon_inactive="mdi:close-circle",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_permission_to_read_data",
        translation_key="gas_permission_to_read_data",
        icon="mdi:eye-check-outline",
        icon_inactive="mdi:eye-off-outline",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_meter_fault_check_allowed",
        translation_key="gas_meter_fault_check_allowed",
        icon="mdi:meter-gas",
        icon_inactive="mdi:meter-gas-outline",
        service_name=SERVICE_NAME_GAS,
    ),
    LianderBinaryEntityDescription(
        key="gas_smart_meter",
        translation_key="gas_smart_meter",
        icon="mdi:meter-gas",
        icon_inactive="mdi:meter-gas-outline",
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

        self._attr_is_on = self._get_is_on()

    @property
    def icon(self) -> str | None:  # type: ignore[override]
        """Return the icon depending on sensor activity."""
        icon_inactive = getattr(self.entity_description, "icon_inactive", None)
        if icon_inactive is not None and self.is_inactive():
            return icon_inactive
        return self.entity_description.icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update binary state once through the coordinator's managed listener."""
        self._attr_is_on = self._get_is_on()
        super()._handle_coordinator_update()

    def is_inactive(self) -> bool:
        """Determine if the sensor is active."""
        return not getattr(self, "_attr_is_on", False)

    def _get_is_on(self) -> bool | None:
        """Return validated booleans, retaining unknown for absent API fields."""
        connection = get_connection(
            self.coordinator.data, self.entity_description.service_name
        )
        if connection is None:
            return None

        key = self.entity_description.key.removeprefix("gas_")
        connection_fields = {
            "contract_active": "contract",
            "permission_to_read_data": "toestemmingVoorUitlezen",
            "meter_fault_check_allowed": "meterstoringscheckToegestaan",
            "smart_meter_request_allowed": "nieuweSlimmeMeterAanvragenToegestaan",
            "backfeeding_energy": "levertTerug",
        }
        if key == "status":
            status = connection.get("status")
            return status == "In bedrijf" if isinstance(status, str) else None
        if key in connection_fields:
            value = connection.get(connection_fields[key])
            return value if isinstance(value, bool) else None

        meter_fields = {
            "smart_meter": "slimmeMeter",
            "gprs": "gprs",
            "analog": "analoog",
            "suitable_for_backfeeding": "geschiktVoorTerugleveren",
            "suitable_for_dual_tariff": "geschiktVoorDubbeltarief",
            "net_metering": "salderingsregeling",
        }
        if key in meter_fields:
            meter = get_first_meter(connection)
            value = meter.get(meter_fields[key]) if meter is not None else None
            return value if isinstance(value, bool) else None

        _LOGGER.warning("Unknown binary sensor key: %s", self.entity_description.key)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return attribution without duplicating raw personal account payloads."""
        return {"attribution": ATTRIBUTION}

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
