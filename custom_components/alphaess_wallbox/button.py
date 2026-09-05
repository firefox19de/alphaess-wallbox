"""Button-Platform fuer die AlphaESS Wallbox Integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = coordinator.client
    device_info = DeviceInfo(
        identifiers={("alphaess", client.ev_charger_sn)},
        name=f"Alpha ESS Charger : {client.ev_charger_sn}",
        manufacturer="Alpha ESS",
        model="SMILE-EVCT11",
    )
    async_add_entities([AlphaESSFetchStatusButton(coordinator, device_info, entry.entry_id)], True)


class AlphaESSFetchStatusButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "fetch_status"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, device_info, entry_id: str):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_fetch_status"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
