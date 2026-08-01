"""Button platform for AlphaESS Wallbox integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AlphaESS Wallbox button platform."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    async_add_entities([AlphaESSFetchStatusButton(api, device_info)], True)


class AlphaESSFetchStatusButton(ButtonEntity):
    """Representation of a button to fetch latest status from Web-API."""

    _attr_has_entity_name = True
    _attr_name = "Werte aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, api, device_info):
        """Initialize the button."""
        self._api = api
        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_info['identifiers']}_fetch_status"

    async def async_press(self) -> None:
        """Handle the button press."""
        # Holt den aktuellen Status von der Web-API und aktualisiert die HA-Entitäten
        await self._api.async_update_status()