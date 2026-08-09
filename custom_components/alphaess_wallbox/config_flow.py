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
            base_url = user_input.get(CONF_URL, "https://eurcloud.alphaess.com").rstrip("/")
            client = AlphaWebApiClient(
                self.hass,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                base_url=base_url,
            )
            success = await client.login()
            await client.close()

            if success:
                return self.async_create_entry(
                    title=f"AlphaESS Web ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_URL: base_url,
                    },
                )

            errors["base"] = "invalid_auth"

        # Formular-Schema definieren (str statt vol.Url() behebt den 500-Serverfehler)
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_URL, default="https://eurcloud.alphaess.com"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
