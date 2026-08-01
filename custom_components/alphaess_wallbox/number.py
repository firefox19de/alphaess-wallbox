import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    # Warten, bis System- & Wallbox-SN geladen sind
    await client.load_system_and_charger()
    async_add_entities([AlphaWallboxCurrentNumber(client, entry.entry_id)])

class AlphaWallboxCurrentNumber(NumberEntity):
    def __init__(self, api_client, entry_id: str):
        self._api = api_client
        sn_prefix = (api_client.system_sn or "alphaess").lower()
        
        # Name und Unique ID an Charles-Präfix anpassen
        self._attr_name = f"EV Charger Max Current Setting"
        self._attr_unique_id = f"{entry_id}_{sn_prefix}_ev_charger_max_current_setting"
        self._attr_native_min_value = 6
        self._attr_native_max_value = 16
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "A"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 16
        self._attr_icon = "mdi:current-ac"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Koppelt die Entität direkt an das Gerät in Home Assistant."""
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
        if status and "max_current" in status and status["max_current"] > 0:
            self._attr_native_value = status["max_current"]

    async def async_set_native_value(self, value: float) -> None:
        target_current = int(value)
        _LOGGER.info("Setting Wallbox Current to %sA", target_current)
        success = await self._api.set_charging_current(target_current)
        if success:
            self._attr_native_value = target_current
            self.async_write_ha_state()