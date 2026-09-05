"""Number entity for setting AlphaESS Wallbox charge current."""
import logging
from homeassistant.components.number import NumberEntity
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
    """Set up AlphaESS Wallbox number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AlphaESSDataUpdateCoordinator = data["coordinator"]

    async_add_entities([AlphaESSChargeCurrentNumber(coordinator, entry)])


class AlphaESSChargeCurrentNumber(CoordinatorEntity, NumberEntity):
    """Representation of EV Charge Current setting."""

    _attr_has_entity_name = True
    _attr_name = "Ladestrom"
    _attr_native_min_value = 6.0
    _attr_native_max_value = 16.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "A"
    _attr_icon = "mdi:current-ac"

    def __init__(
        self,
        coordinator: AlphaESSDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the charge current entity."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_unique_id = f"{entry.entry_id}_charge_current"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current charge current value."""
        if self.coordinator.data and "chargeCurrent" in self.coordinator.data:
            val = self.coordinator.data["chargeCurrent"]
            if val is not None:
                return float(val)
        return 6.0

    async def async_set_native_value(self, value: float) -> None:
        """Set new charge current with 0.1A precision."""
        target_current = round(value, 1)
        _LOGGER.debug("Setting AlphaESS Wallbox charge current to %.1f A", target_current)
        
        # Optimistisches lokales Update, um ein Verspringen vor dem Refresh zu verhindern
        if self.coordinator.data:
            self.coordinator.data["chargeCurrent"] = target_current

        success = await self.api.async_set_ev_charge_current(target_current)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set charge current to %.1f A", target_current)