import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL

from .api import AlphaWebApiClient

DOMAIN = "alphaess_wallbox"
PLATFORMS = ["select", "number"]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet die Integration ueber die Config Flow Daten ein."""
    client = AlphaWebApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        base_url=entry.data.get(CONF_URL, "https://eurcloud.alphaess.com")
    )
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    # Lädt select.py und number.py
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Integration sauber."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok