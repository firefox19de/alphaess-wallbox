"""Number-Entity fuer den Ladestrom der AlphaESS Wallbox."""
import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
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
    """Set up number entities for the AlphaESS wallbox."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = coordinator.client

    device_info = DeviceInfo(
        identifiers={("alphaess", client.ev_charger_sn)},
        name=f"Alpha ESS Charger : {client.ev_charger_sn}",
        manufacturer="Alpha ESS",
        model="SMILE-EVCT11",
    )

    async_add_entities(
        [AlphaWallboxCurrentNumber(coordinator, device_info, entry.entry_id)],
        True,
    )


class AlphaWallboxCurrentNumber(CoordinatorEntity, NumberEntity):
    """Steuert die maximale Ladestromstaerke."""

    _attr_has_entity_name = True
    _attr_translation_key = "maxcurrent"
    _attr_icon = "mdi:current-ac"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 6
    _attr_native_max_value = 16
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "A"

    def __init__(self, coordinator, device_info, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_ev_charger_max_current_setting"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get("chargeCurrent")
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        target = round(value, 1)
        _LOGGER.debug("Setting Wallbox current to %.1fA", target)
        if self.coordinator.data is not None:
            self.coordinator.data["chargeCurrent"] = target
        self.async_write_ha_state()
        success = await self.coordinator.client.async_set_ev_charge_current(target)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set charge current to %.1fA", target)