ï»¿import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN if "const" in globals() else "alphaess_wallbox"

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Number-EntitÃ¤ten fÃ¼r die Wallbox ein."""
    client = hass.data["alphaess_wallbox"][entry.entry_id]
    sys_sn = entry.data.get("sys_sn", entry.entry_id)

    async_add_entities([AlphaWallboxCurrentNumber(client, sys_sn)])

class AlphaWallboxCurrentNumber(NumberEntity):
    """Steuerung des Maximalstroms (6A - 32A)."""
    def __init__(self, api_client, sys_sn):
        self._api = api_client
        self._sys_sn = sys_sn
        self._attr_name = "Wallbox Maximalstrom"
        self._attr_unique_id = f"{sys_sn}_wallbox_max_current"
        self._attr_native_min_value = 6
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "A"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 16

    async def async_set_native_value(self, value: float) -> None:
        target_current = int(value)
        _LOGGER.info(f"Setting Wallbox Current to {target_current}A")
        
        await self._api.set_charging_current(self._sys_sn, target_current)
        self._attr_native_value = target_current
        self.async_write_ha_state()