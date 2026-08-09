import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

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
        manufacturer="AlphaESS",
        model="SMILE-EVCT11",
    )

    async_add_entities(
        [AlphaWallboxCurrentNumber(coordinator, device_info, entry.entry_id)],
        True,
    )


class AlphaWallboxCurrentNumber(CoordinatorEntity, NumberEntity):
    """Control the maximum charging current."""

    _attr_has_entity_name = True
    _attr_translation_key = "maxcurrent"
    _attr_icon = "mdi:current-ac"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 6
    _attr_native_max_value = 16
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "A"

    def __init__(self, coordinator, device_info, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_ev_charger_max_current_setting"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("max_current")

    async def async_set_native_value(self, value: float) -> None:
        target_current = int(value)
        _LOGGER.debug("Setting Wallbox current to %sA", target_current)

        success = await self.coordinator.client.set_charging_current(target_current)
        if success and self.coordinator.data is not None:
            self.coordinator.data["max_current"] = target_current
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
