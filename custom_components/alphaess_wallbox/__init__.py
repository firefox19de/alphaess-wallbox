"""AlphaESS Wallbox Integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AlphaESSApiClient
from .coordinator import AlphaESSDataUpdateCoordinator
from .const import DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["select", "number", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet die Integration ueber die Config Flow Daten ein."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = AlphaESSApiClient(
        session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    if not await client.async_login():
        _LOGGER.error("AlphaESS: Login fehlgeschlagen beim Setup.")
        return False

    if not await client.async_get_env_and_site_details():
        _LOGGER.error("AlphaESS: Systemdaten konnten nicht geladen werden.")
        return False

    coordinator = AlphaESSDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Integration sauber."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok