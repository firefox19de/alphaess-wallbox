ï»¿import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

MODE_OPTIONS = {
    "Langsamladung (Eco 1)": 1,
    "Schonladung (Eco 2)": 2,
    "Schnellladung (Eco 3)": 3,
    "Custom / Manuell (evcc-Steuerung)": 4
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Select-EntitÃ¤ten fÃ¼r die Wallbox ein."""
    client = hass.data["alphaess_wallbox"][entry.entry_id]
    sys_sn = entry.data.get("sys_sn", entry.entry_id)
    charger_sn = entry.data.get("charger_sn", "default_charger")

    async_add_entities([
        AlphaWallboxModeSelect(client, sys_sn),
        AlphaWallboxPhaseSelect(hass, client, sys_sn, charger_sn)
    ])

class AlphaWallboxModeSelect(SelectEntity):
    """Lademodus Auswahl (Eco vs Custom)."""
    def __init__(self, api_client, sys_sn):
        self._api = api_client
        self._sys_sn = sys_sn
        self._attr_name = "Wallbox Lademodus"
        self._attr_unique_id = f"{sys_sn}_wallbox_mode"
        self._attr_options = list(MODE_OPTIONS.keys())
        self._attr_current_option = "Custom / Manuell (evcc-Steuerung)"

    async def async_select_option(self, option: str) -> None:
        mode_code = MODE_OPTIONS.get(option, 4)
        _LOGGER.info(f"Setting Wallbox Mode to: {option} ({mode_code})")
        
        await self._api.set_charge_mode(self._sys_sn, mode_code)
        self._attr_current_option = option
        self.async_write_ha_state()

class AlphaWallboxPhaseSelect(SelectEntity):
    """Phasenwahl mit integrierten Hardware Guard-Delays."""
    def __init__(self, hass, api_client, sys_sn, charger_sn):
        self.hass = hass
        self._api = api_client
        self._sys_sn = sys_sn
        self._charger_sn = charger_sn
        self._attr_name = "Wallbox Phasen"
        self._attr_unique_id = f"{sys_sn}_wallbox_phases"
        self._attr_options = ["1 Phase", "3 Phasen"]
        self._attr_current_option = "3 Phasen"

    async def async_select_option(self, option: str) -> None:
        target_phases = 1 if option == "1 Phase" else 3
        _LOGGER.info(f"Initiating phase switch to {target_phases}P with safety delays...")

        # 1. Stop Charging via Charles Integration Button
        await self.hass.services.async_call(
            "button", "press",
            {"entity_id": f"button.{self._charger_sn.lower()}_stop_charging"}
        )

        # Guard Delay 1: Relais entlasten
        await asyncio.sleep(3.5)

        # 2. Phasen Umschaltung Ã¼ber Web-API
        await self._api.set_phases(self._sys_sn, target_phases)
        self._attr_current_option = option
        self.async_write_ha_state()

        # Guard Delay 2: Hardware-Stabilisierung
        await asyncio.sleep(6.0)

        # 3. Resume Charging
        await self.hass.services.async_call(
            "button", "press",
            {"entity_id": f"button.{self._charger_sn.lower()}_start_charging"}
        )