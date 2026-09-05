"""Button entities for AlphaESS Wallbox charge control."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlphaESSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AlphaESS Wallbox button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AlphaESSDataUpdateCoordinator = data["coordinator"]

    async_add_entities([
        AlphaESSStartChargeButton(coordinator, entry),
        AlphaESSStopChargeButton(coordinator, entry),
    ])


class AlphaESSStartChargeButton(CoordinatorEntity, ButtonEntity):
    """Button to start EV charging."""

    _attr_has_entity_name = True
    _attr_name = "Ladevorgang Starten"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(
        self,
        coordinator: AlphaESSDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize start button."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_unique_id = f"{entry.entry_id}_start_charge"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.debug("Triggering EV charge START")
        success = await self.api.async_set_ev_charge_ctrl("START")
        if success:
            await self.coordinator.async_request_refresh()


class AlphaESSStopChargeButton(CoordinatorEntity, ButtonEntity):
    """Button to stop EV charging."""

    _attr_has_entity_name = True
    _attr_name = "Ladevorgang Stoppen"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(
        self,
        coordinator: AlphaESSDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize stop button."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_unique_id = f"{entry.entry_id}_stop_charge"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.debug("Triggering EV charge STOP")
        success = await self.api.async_set_ev_charge_ctrl("STOP")
        if success:
            await self.coordinator.async_request_refresh()