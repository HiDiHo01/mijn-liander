# __init__.py
"""The Mijn Liander integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import LianderDataUpdateCoordinator
from .gas import has_active_gas_contract
from .migration import async_migrate_registry, remove_inactive_gas_registry_entries

_LOGGER = logging.getLogger(__name__)


async def async_setup_coordinator(hass: HomeAssistant, entry: ConfigEntry
                                  ) -> LianderDataUpdateCoordinator:
    """Set up the Liander data update coordinator."""
    coordinator = LianderDataUpdateCoordinator(hass, entry)

    # Optionally, you can perform additional setup here
    # For example, you might want to perform an initial update to ensure data is available

    # Optionally, perform an initial update to ensure data is available at setup
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data: %s", err)
        raise

    # await coordinator.async_refresh()  # Initial fetch to populate data
    return coordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Mijn Liander component from configuration.yaml."""
    # This method sets up the component from YAML configuration
    # Example: setting up any services or initialization logic here

    # Register any services if needed:
    # hass.services.async_register(DOMAIN, "example_service", example_service_handler)

    # Returning True indicates that the setup was successful
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mijn Liander from a config entry."""
    _LOGGER.debug(
        "Setting up Liander component for entry: %s", entry.entry_id)
    # Retrieve configuration data from entry
    # username = entry.data.get("username")
    # password = entry.data.get("password")

    # Setup coordinator
    try:
        coordinator = await async_setup_coordinator(hass, entry)
    except Exception as err:
        _LOGGER.error("Error setting up coordinator: %s", err)
        return False

    # Avoid overwriting hass.data[DOMAIN] entirely
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await async_migrate_registry(hass, entry)
    gas_contract_active = has_active_gas_contract(coordinator.data)
    if not gas_contract_active:
        remove_inactive_gas_registry_entries(hass, entry)
    # hass.data[DOMAIN]["credentials"] = {
    #     "username": username,
    #     "password": password
    # }

    # Forward the entry to other platforms (e.g., sensor, binary_sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_monitor_gas_contract(
        hass, entry, coordinator, gas_contract_active
    )

    # Optionally, update the entry's unique ID and title
    # hass.config_entries.async_update_entry(entry, unique_id="mijn_liander")
    # entry.title = "Mijn Liander"
    # Returning True indicates that the setup was successful.
    return True


def _async_monitor_gas_contract(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: LianderDataUpdateCoordinator,
    configured_gas_contract_active: bool,
) -> None:
    """Reload platforms when the account gains or loses an active gas contract."""
    gas_contract_active = configured_gas_contract_active
    reload_pending = False

    async def reload_entry(previous_state: bool) -> None:
        """Reload the config entry and allow retry if the reload fails."""
        nonlocal gas_contract_active, reload_pending
        try:
            if not await hass.config_entries.async_reload(entry.entry_id):
                _LOGGER.error(
                    "Could not reload Mijn Liander after the gas contract "
                    "state changed for config entry %s",
                    entry.entry_id,
                )
                gas_contract_active = previous_state
        finally:
            reload_pending = False

    def handle_coordinator_update() -> None:
        """Reload entity platforms when gas contract availability changes."""
        nonlocal gas_contract_active, reload_pending
        current_state = has_active_gas_contract(coordinator.data)
        if current_state == gas_contract_active or reload_pending:
            return

        previous_state = gas_contract_active
        gas_contract_active = current_state
        reload_pending = True
        hass.async_create_task(reload_entry(previous_state))

    entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading a config entry."""
    _LOGGER.debug("Unloading entry: %s", entry.entry_id)

    # Remove coordinator from hass.data
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unload the platforms for the entry (e.g., sensor, binary_sensor)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Return the result of unloading
    return unload_ok
