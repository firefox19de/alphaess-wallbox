"""Config flow for AlphaESS Wallbox integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AlphaESSApiClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

class AlphaESSWallboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AlphaESS Wallbox."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = AlphaESSApiClient(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            if await api.async_login():
                return self.async_create_entry(
                    title=f"AlphaESS Wallbox ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )