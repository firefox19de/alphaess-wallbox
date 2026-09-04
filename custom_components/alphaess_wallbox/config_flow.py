import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import AlphaWebApiClient
from .const import DOMAIN


class AlphaWallboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handhabt den Einrichtungs-Dialog in Home Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            base_url = user_input.get(CONF_URL, "https://platform-eur.alphaess.com").rstrip("/")
            client = AlphaWebApiClient(
                self.hass,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                base_url=base_url,
            )

            try:
                success = await client.login()
                if success:
                    await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"AlphaESS Web ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_URL: base_url,
                        },
                    )
                errors["base"] = "cannot_connect"
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_URL, default="https://platform-eur.alphaess.com"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )