"""Button platform for AlphaESS Wallbox integration."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AlphaESS Wallbox button platform."""
    client = hass.data[DOMAIN][entry.entry_id]
    await client.load_system_and_charger()
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, client.ev_charger_sn)},
        name=f"Alpha ESS Charger : {client.ev_charger_sn}",
        manufacturer="AlphaESS",
        model="SMILE-EVCT11",
    )
    
    async_add_entities([AlphaESSFetchStatusButton(client, device_info, entry.entry_id)], True)


class AlphaESSFetchStatusButton(ButtonEntity):
    """Representation of a button to fetch latest status from Web-API."""

    _attr_has_entity_name = True
    _attr_translation_key = "fetch_status"
    _attr_icon = "mdi:refresh"

    def __init__(self, api_client, device_info, entry_id: str):
        """Initialize the button."""
        self._api = api_client
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_fetch_status"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._api.get_wallbox_status()