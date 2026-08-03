from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AlphaWebApiClient

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)


class AlphaESSDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Koordiniert den abgerufenen Zustandscache für die AlphaESS Wallbox."""

    def __init__(self, hass: HomeAssistant, client: AlphaWebApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="AlphaESS Wallbox",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Fetch data from API with automatic re-authentication on failure."""
        data = await self.client.get_wallbox_status()
        if data is None:
            _LOGGER.warning("AlphaESS Session abgelaufen oder API-Fehler. Führe Re-Login aus...")
            if await self.client.login():
                _LOGGER.info("Re-Login erfolgreich. Erneute Datenabfrage...")
                data = await self.client.get_wallbox_status()
        if data is None:
            raise UpdateFailed("AlphaESS Web API konnte auch nach Re-Login keine Daten zurückliefern")
        return data