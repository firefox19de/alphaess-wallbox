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
    "Gruenes Laden - Langsam": 1,
    "Gruenes Laden - Standard": 2,
    "Gruenes Laden - Schnell": 3,
    "Leistung angeben": 4,
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}

PHASE_MAP = {
    "Einphasig": 1,
    "Zweiphasig": 2,
    "Dreiphasig": 3,
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
        self._attr_current_option = "Leistung angeben"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    @property
    def current_option(self) -> str | None:
        """Return currently selected mode."""
        if self.coordinator.data and "chargeMode" in self.coordinator.data:
            try:
                mode_int = int(self.coordinator.data["chargeMode"])
                val = REVERSE_MODE_MAP.get(mode_int)
                if val:
                    self._attr_current_option = val
            except (ValueError, TypeError):
                pass
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Change charge mode."""
        mode_val = MODE_MAP.get(option)
        if mode_val:
            _LOGGER.debug("Setting AlphaESS Wallbox charge mode to %s (%d)", option, mode_val)
            self._attr_current_option = option
            if self.coordinator.data:
                self.coordinator.data["chargeMode"] = mode_val
            self.async_write_ha_state()

            success = await self.api.async_set_ev_charge_mode(mode_val)
            if success:
                await self.coordinator.async_request_refresh()


class AlphaESSPhaseSelect(CoordinatorEntity, SelectEntity):
    """Select entity for OBC phase configuration."""

    _attr_has_entity_name = True
    _attr_name = "OBC-Phasenauswahl"
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
        self._attr_current_option = "Dreiphasig"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "AlphaESS Wallbox",
            "manufacturer": "AlphaESS",
        }

    @property
    def current_option(self) -> str | None:
        """Return active phase setting."""
        if self.coordinator.data and "obcPhase" in self.coordinator.data:
            try:
                phase_int = int(self.coordinator.data["obcPhase"])
                val = REVERSE_PHASE_MAP.get(phase_int)
                if val:
                    self._attr_current_option = val
            except (ValueError, TypeError):
                pass
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Change phase configuration."""
        phase_val = PHASE_MAP.get(option)
        if phase_val:
            _LOGGER.debug("Setting AlphaESS Wallbox phases to %s (%d)", option, phase_val)
            self._attr_current_option = option
            if self.coordinator.data:
                self.coordinator.data["obcPhase"] = phase_val
            self.async_write_ha_state()

            success = await self.api.async_set_ev_phases(phase_val)
            if success:
                await self.coordinator.async_request_refresh()