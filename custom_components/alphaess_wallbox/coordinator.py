"""Coordinator for AlphaESS Wallbox integration."""
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AlphaESSApiClient
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class AlphaESSDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching AlphaESS Wallbox data."""

    def __init__(self, hass: HomeAssistant, api: AlphaESSApiClient) -> None:
        """Initialize coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from AlphaESS Cloud API."""
        try:
            status_data = await self.api.async_get_ev_status()
            if not status_data:
                _LOGGER.warning("Empty response received from AlphaESS Wallbox API")
            return status_data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with AlphaESS API: {err}") from err