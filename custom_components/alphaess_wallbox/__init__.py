import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import AlphaWebApiClient
from .coordinator import AlphaESSDataUpdateCoordinator
from .const import DOMAIN, DEFAULT_BASE_URL

PLATFORMS = ["select", "number", "button"]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet die Integration über die Config Flow Daten ein."""
    client = AlphaWebApiClient(
        hass,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        base_url=entry.data.get(CONF_URL, DEFAULT_BASE_URL),
    )

    if not await client.login():
        raise ConfigEntryAuthFailed("AlphaESS Login fehlgeschlagen – Zugangsdaten prüfen")

    if not await client.load_system_and_charger():
        raise ConfigEntryNotReady("AlphaESS Platform API konnte Systemdaten nicht laden")

    coordinator = AlphaESSDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Integration sauber."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
    return unload_ok