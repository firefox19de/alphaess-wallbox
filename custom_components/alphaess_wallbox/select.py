import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

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
    client = hass.data[DOMAIN][entry.entry_id]
    await client.load_system_and_charger()
    async_add_entities([
        AlphaESSModeSelect(client, entry.entry_id),
        AlphaESSPhaseSelect(client, entry.entry_id),
    ])

class AlphaESSModeSelect(SelectEntity):
    def __init__(self, api_client, entry_id: str):
        self._api = api_client
        sn_prefix = (api_client.system_sn or "alphaess").lower()
        self._attr_name = "EV Charger Charge Mode"
        self._attr_unique_id = f"{entry_id}_{sn_prefix}_ev_charger_charge_mode"
        self._attr_options = list(MODE_MAP.keys())
        self._attr_current_option = "Custom / Manuell (evcc-Steuerung)"
        self._attr_icon = "mdi:ev-station"

    @property
    def device_info(self) -> DeviceInfo | None:
        if self._api.ev_charger_sn:
            return DeviceInfo(
                identifiers={(DOMAIN, self._api.ev_charger_sn)},
                name=f"Alpha ESS Charger : {self._api.ev_charger_sn}",
                manufacturer="AlphaESS",
                model="SMILE-EVCT11",
            )
        return None

    async def async_update(self) -> None:
        status = await self._api.get_wallbox_status()
        if status and "charging_mode" in status:
            mode_code = status["charging_mode"]
            if mode_code in REVERSE_MODE_MAP:
                self._attr_current_option = REVERSE_MODE_MAP[mode_code]

    async def async_select_option(self, option: str) -> None:
        mode_code = MODE_MAP.get(option, 4)
        success = await self._api.set_charge_mode(mode_code)
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()

class AlphaESSPhaseSelect(SelectEntity):
    def __init__(self, api_client, entry_id: str):
        self._api = api_client
        sn_prefix = (api_client.system_sn or "alphaess").lower()
        self._attr_name = "EV Charger Phases"
        self._attr_unique_id = f"{entry_id}_{sn_prefix}_ev_charger_phases"
        self._attr_options = list(PHASE_MAP.keys())
        self._attr_current_option = "3-phasig"
        self._attr_icon = "mdi:phase-change"

    @property
    def device_info(self) -> DeviceInfo | None:
        if self._api.ev_charger_sn:
            return DeviceInfo(
                identifiers={(DOMAIN, self._api.ev_charger_sn)},
                name=f"Alpha ESS Charger : {self._api.ev_charger_sn}",
                manufacturer="AlphaESS",
                model="SMILE-EVCT11",
            )
        return None

    async def async_update(self) -> None:
        status = await self._api.get_wallbox_status()
        if status and "phase" in status:
            phase_code = status["phase"]
            if phase_code in REVERSE_PHASE_MAP:
                self._attr_current_option = REVERSE_PHASE_MAP[phase_code]

    async def async_select_option(self, option: str) -> None:
        phase_code = PHASE_MAP.get(option, 3)
        success = await self._api.set_phases(phase_code)
        if success:
            self._attr_current_option = option
            self.async_write_ha_state()