"""Select entities for AlphaESS Wallbox mode and phase control."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlphaESSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "Eco-Slow": 1,
    "Eco-General": 2,
    "Eco-Quick": 3,
    "Power": 4,
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}

PHASE_MAP = {
    "1 Phase": 1,
    "3 Phasen": 3,
}
REVERSE_PHASE_MAP = {v: k for k, v in PHASE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AlphaESS Wallbox select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AlphaESSDataUpdateCoordinator = data["coordinator"]

    async_add_entities([
        AlphaESSChargeModeSelect(coordinator, entry),
        AlphaESSPhaseSelect(coordinator, entry),
    ])


class AlphaESSChargeModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for EV charge mode."""

    _attr_has_entity_name = True
    _attr_name = "Lademodus"
    _attr_icon = "mdi:ev-station"
    _attr_options = list(MODE_MAP.keys())

    def __init__(
        self,
        coordinator: AlphaESSDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the charge mode select."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_unique_id = f"{entry.entry_id}_charge_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    @property
    def current_option(self) -> str | None:
        """Return currently selected mode."""
        if self.coordinator.data:
            mode_int = self.coordinator.data.get("chargeMode", 4)
            return REVERSE_MODE_MAP.get(mode_int, "Power")
        return "Power"

    async def async_select_option(self, option: str) -> None:
        """Change charge mode."""
        mode_val = MODE_MAP.get(option)
        if mode_val:
            _LOGGER.debug("Setting AlphaESS Wallbox charge mode to %s (%d)", option, mode_val)
            success = await self.api.async_set_ev_charge_mode(mode_val)
            if success:
                await self.coordinator.async_request_refresh()


class AlphaESSPhaseSelect(CoordinatorEntity, SelectEntity):
    """Select entity for 1-Phase / 3-Phase switching."""

    _attr_has_entity_name = True
    _attr_name = "Phasen"
    _attr_icon = "mdi:sine-wave"
    _attr_options = list(PHASE_MAP.keys())

    def __init__(
        self,
        coordinator: AlphaESSDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize phase select."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_unique_id = f"{entry.entry_id}_charge_phase"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    @property
    def current_option(self) -> str | None:
        """Return active phase setting."""
        if self.coordinator.data:
            phase_int = self.coordinator.data.get("obcPhase", 3)
            return REVERSE_PHASE_MAP.get(phase_int, "3 Phasen")
        return "3 Phasen"

    async def async_select_option(self, option: str) -> None:
        """Change phase configuration."""
        phase_val = PHASE_MAP.get(option)
        if phase_val:
            _LOGGER.debug("Setting AlphaESS Wallbox phases to %s (%d)", option, phase_val)
            success = await self.api.async_set_ev_phases(phase_val)
            if success:
                await self.coordinator.async_request_refresh()