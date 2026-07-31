import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL

from .api import AlphaWebApiClient

DOMAIN = "alphaess_wallbox"

class AlphaWallboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt den Einrichtungs-Dialog in Home Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Login testen
            client = AlphaWebApiClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                base_url=user_input[CONF_URL]
            )
            success = await client.login()
            await client.close()

            if success:
                return self.async_create_entry(
                    title=f"AlphaESS Web ({user_input[CONF_USERNAME]})",
                    data=user_input
                )

            errors["base"] = "invalid_auth"

        # Formular-Schema definieren
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_URL, default="https://eurcloud.alphaess.com"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )