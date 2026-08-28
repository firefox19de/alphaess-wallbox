import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, build_device_info

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "Eco / Langsamladung (Nur PV)": 1,
    "Eco / Schonladung (PV + Akku)": 2,
    "Eco / Schnellladung": 3,
    "Custom / Manuell (evcc-Steuerung)": 4,
}
REVERSE_MODE_MAP = {v: k for k, v in MODE_MAP.items()}

PHASE_MAP = {
    "1-phasig": 1,
    "3-phasig": 3,
}
REVERSE_PHASE_MAP = {v: k for k, v in PHASE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for the AlphaESS wallbox."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = coordinator.client

    device_info = build_device_info(client.ev_charger_sn)

    async_add_entities(
        [
            AlphaESSModeSelect(coordinator, device_info, entry.entry_id),
            AlphaESSPhaseSelect(coordinator, device_info, entry.entry_id),
        ],
        True,
    )


class AlphaESSModeSelect(CoordinatorEntity, SelectEntity):
    """Auswahl des Lademodus."""

    _attr_has_entity_name = True
    _attr_translation_key = "mode"
    _attr_icon = "mdi:ev-station"
    _attr_options = list(MODE_MAP.keys())

    def __init__(self, coordinator, device_info, entry_id: str):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_ev_charger_charge_mode"
        self._attr_current_option = "Custom / Manuell (evcc-Steuerung)"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return REVERSE_MODE_MAP.get(
            self.coordinator.data.get("charging_mode"), self._attr_current_option
        )

    async def async_select_option(self, option: str) -> None:
        mode_code = MODE_MAP.get(option, 4)
        success = await self.coordinator.client.set_charge_mode(mode_code)
        if success and self.coordinator.data is not None:
            self.coordinator.data["charging_mode"] = mode_code
            self._attr_current_option = option
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        elif not success:
            _LOGGER.error("Fehler beim Setzen des Lademodus %s", option)


class AlphaESSPhaseSelect(CoordinatorEntity, SelectEntity):
    """Auswahl der Phasenanzahl."""

    _attr_has_entity_name = True
    _attr_translation_key = "phases"
    _attr_icon = "mdi:phase-change"
    _attr_options = list(PHASE_MAP.keys())

    def __init__(self, coordinator, device_info, entry_id: str):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_ev_charger_phases"
        self._attr_current_option = "3-phasig"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return REVERSE_PHASE_MAP.get(
            self.coordinator.data.get("phase"), self._attr_current_option
        )

    async def async_select_option(self, option: str) -> None:
        phase_code = PHASE_MAP.get(option, 3)
        success = await self.coordinator.client.set_phases(phase_code)
        if success and self.coordinator.data is not None:
            self.coordinator.data["phase"] = phase_code
            self._attr_current_option = option
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        elif not success:
            _LOGGER.error("Fehler beim Setzen der Phasenanzahl %s", option)