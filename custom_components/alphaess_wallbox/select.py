import logging
from homeassistant.components.select import SelectEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MODE_MAP = {
    "Eco / Langsamladung (Nur PV)": 1,
    "Eco / Schonladung (PV + Akku)": 2,
    "Eco / Schnellladung": 3,
    "Custom / Manuell (evcc-Steuerung)": 4,
}

class AlphaESSModeSelect(SelectEntity):
    """Select Entity fuer den AlphaESS Lademodus."""

    def __init__(self, coordinator, api, entry):
        self.coordinator = coordinator
        self._api = api
        self._attr_name = "AlphaESS Lademodus"
        self._attr_unique_id = f"{entry.entry_id}_charge_mode"
        self._attr_options = list(MODE_MAP.keys())

    @property
    def current_option(self) -> str | None:
        mode_code = self.coordinator.data.get("charging_mode") if self.coordinator.data else None
        for name, code in MODE_MAP.items():
            if code == mode_code:
                return name
        return None

    async def async_select_option(self, option: str) -> None:
        """Ändert den Lademodus."""
        mode_code = MODE_MAP.get(option, 4)
        # HIER FIX: self._sys_sn entfernt
        success = await self._api.set_charge_mode(mode_code)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Fehler beim Setzen des Lademodus auf %s", option)