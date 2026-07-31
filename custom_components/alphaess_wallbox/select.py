import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "Eco / Langsamladung (Nur PV)": 1,
    "Eco / Schonladung (PV + Akku)": 2,
    "Eco / Schnellladung": 3,
    "Custom / Manuell (evcc-Steuerung)": 4,
}

PHASE_MAP = {
    "1-phasig": 1,
    "3-phasig": 3,
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Select-Entitaeten fuer die Wallbox ein."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        AlphaESSModeSelect(client, entry.entry_id),
        AlphaESSPhaseSelect(client, entry.entry_id),
    ])


class AlphaESSModeSelect(SelectEntity):
    """Select Entity fuer den AlphaESS Lademodus."""

    def __init__(self, api_client, entry_id: str):
        self._api = api_client
        self._attr_name = "AlphaESS Lademodus"
        self._attr_unique_id = f"{entry_id}_charge_mode"
        self._attr_options = list(MODE_MAP.keys())
        self._attr_current_option = "Custom / Manuell (evcc-Steuerung)"

    async def async_select_option(self, option: str) -> None:
        """Aendert den Lademodus."""
        mode_code = MODE_MAP.get(option, 4)
        success = await self._api.set_charge_mode(mode_code)
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Fehler beim Setzen des Lademodus auf %s", option)


class AlphaESSPhaseSelect(SelectEntity):
    """Select Entity fuer die Phasenumschaltung (1-phasig / 3-phasig)."""

    def __init__(self, api_client, entry_id: str):
        self._api = api_client
        self._attr_name = "AlphaESS Phasen"
        self._attr_unique_id = f"{entry_id}_charging_phase"
        self._attr_options = list(PHASE_MAP.keys())
        self._attr_current_option = "3-phasig"

    async def async_select_option(self, option: str) -> None:
        """Aendert die Phasenanzahl."""
        phase_code = PHASE_MAP.get(option, 3)
        success = await self._api.set_phases(phase_code)
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Fehler beim Setzen der Phasen auf %s", option)