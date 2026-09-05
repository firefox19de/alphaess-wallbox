"""Config Flow fuer die AlphaESS Wallbox Integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AlphaESSApiClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})


class AlphaWallboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt den Einrichtungs-Dialog in Home Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = AlphaESSApiClient(
                session,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            success = await client.async_login()

            if success:
                return self.async_create_entry(
                    title=f"AlphaESS Wallbox ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )