"""Coordinator fuer die AlphaESS Wallbox Integration."""
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AlphaESSApiClient
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AlphaESSDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Koordiniert die abgerufenen Daten der AlphaESS Wallbox."""

    def __init__(self, hass: HomeAssistant, client: AlphaESSApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="AlphaESS Wallbox",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Fetch data from API with automatic re-authentication on failure."""
        data = await self.client.async_get_ev_status()
        if data is None:
            _LOGGER.warning("AlphaESS: Session abgelaufen oder API-Fehler. Fuehre Re-Login aus...")
            if await self.client.async_login():
                _LOGGER.info("AlphaESS: Re-Login erfolgreich. Erneute Datenabfrage...")
                data = await self.client.async_get_ev_status()
        if data is None:
            raise UpdateFailed("AlphaESS Web API konnte auch nach Re-Login keine Daten liefern.")
        return data