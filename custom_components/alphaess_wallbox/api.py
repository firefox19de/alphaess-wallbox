"""API Client for AlphaESS Wallbox Integration."""
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://platform-eur.alphaess.com"
LOGIN_URL = "https://cloud.alphaess.com/login"
API_PILOT_URL = "https://cloud.alphaess.com/api/usercenter/cloud/user/pilot"
API_SESSION_URL = "https://platform-eur.alphaess.com/api/users-center/sessions"
API_SITES_URL = "https://platform-eur.alphaess.com/api/internal/v1/sites"
API_EV_URL = "https://platform-eur.alphaess.com/api/internal/v1/ev-charger"
API_ESS_URL = "https://platform-eur.alphaess.com/api/internal/v1/ess"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://portal.alphaess.com",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}

def _extract_data(res_json):
    """Extract inner data payload if present, otherwise return full dict."""
    if isinstance(res_json, dict) and "data" in res_json:
        return res_json["data"]
    return res_json

class AlphaESSApiClient:
    """Client for AlphaESS Cloud API v2."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self._session = session
        self._username = username
        self._password = password
        self._access_token = None
        self._refresh_token = None
        self.site_id = None
        self.system_sn = None
        self.ev_charger_sn = None
        self.has_charging_pile = False

    async def async_login(self) -> bool:
        """Authenticate with AlphaESS cloud API."""
        try:
            # 1. Warm-up Login Page
            await self._session.post(LOGIN_URL, headers=DEFAULT_HEADERS)

            # 2. Pilot Request
            pilot_payload = {"username": self._username, "pilot": False}
            await self._session.post(API_PILOT_URL, json=pilot_payload, headers=DEFAULT_HEADERS)

            # 3. Session Login Request
            session_payload = {
                "type": "password",
                "email": self._username,
                "password": self._password
            }
            async with self._session.post(API_SESSION_URL, json=session_payload, headers=DEFAULT_HEADERS) as resp:
                data = await resp.json()
                res_data = _extract_data(data)
                
                token = res_data.get("accessToken") if isinstance(res_data, dict) else None
                
                if not token:
                    _LOGGER.error("Login failed, missing accessToken: %s", data)
                    return False

                self._access_token = f"Bearer {token}"
                self._refresh_token = res_data.get("refreshToken")
                _LOGGER.debug("Login successful, token stored.")
                return True

        except Exception as err:
            _LOGGER.error("Error during AlphaESS authentication: %s", err)
            return False

    def _get_auth_headers(self) -> dict:
        """Get headers with Bearer token."""
        headers = DEFAULT_HEADERS.copy()
        if self._access_token:
            headers["Authorization"] = self._access_token
        return headers

    async def async_get_env_and_site_details(self) -> bool:
        """Fetch site ID, system SN, and EV charger SN."""
        if not self._access_token:
            if not await self.async_login():
                return False

        try:
            headers = self._get_auth_headers()

            # 1. Sites abrufen
            async with self._session.get(API_SITES_URL, headers=headers) as resp:
                res_json = await resp.json()
                sites = _extract_data(res_json)
                if not isinstance(sites, list) or not sites:
                    _LOGGER.error("No sites found in AlphaESS account.")
                    return False
                self.site_id = sites[0].get("id")

            # 2. Site Details abrufen
            site_url = f"{API_SITES_URL}/{self.site_id}"
            async with self._session.get(site_url, headers=headers) as resp:
                res_json = await resp.json()
                site_details = _extract_data(res_json)
                if isinstance(site_details, dict):
                    self.has_charging_pile = site_details.get("hasChargingPile", False)
                    ess_devices = site_details.get("essDevices", [])
                    if ess_devices:
                        self.system_sn = ess_devices[0].get("sysSn")

            if not self.has_charging_pile:
                _LOGGER.warning("No charging pile detected on site.")
                return False

            # 3. Wallbox Devices abrufen
            devices_url = f"{site_url}/devices"
            async with self._session.get(devices_url, headers=headers) as resp:
                res_json = await resp.json()
                devices_data = _extract_data(res_json)
                if isinstance(devices_data, dict):
                    ess_list = devices_data.get("ess", [])
                    if ess_list and "evChargers" in ess_list[0] and ess_list[0]["evChargers"]:
                        self.ev_charger_sn = ess_list[0]["evChargers"][0].get("sysSn")

            return bool(self.ev_charger_sn)

        except Exception as err:
            _LOGGER.error("Failed to fetch environment and site details: %s", err)
            return False

    async def async_get_ev_status(self) -> dict:
        """Get real-time EV charger status."""
        if not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return {}

        url = f"{API_EV_URL}/{self.ev_charger_sn}/real-status"
        try:
            async with self._session.get(url, headers=self._get_auth_headers()) as resp:
                res_json = await resp.json()
                data = _extract_data(res_json)
                if isinstance(data, dict):
                    return {
                        "status": data.get("status"),
                        "gun_is_lock": data.get("gunIsLock"),
                        "power": data.get("power"),
                    }
                return {}
        except Exception as err:
            _LOGGER.error("Failed to fetch EV charger status: %s", err)
            return {}

    async def async_set_ev_charge_current(self, current: int) -> bool:
        """Set charge current (in Amperes)."""
        if not self.system_sn or not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return False

        url = f"{API_ESS_URL}/{self.system_sn}"
        payload = {
            "evCharger": [
                {
                    "sn": self.ev_charger_sn,
                    "g1T": {
                        "chargeCurrent": current
                    }
                }
            ]
        }
        try:
            async with self._session.patch(url, json=payload, headers=self._get_auth_headers()) as resp:
                return resp.status == 200
        except Exception as err:
            _LOGGER.error("Failed to set charge current: %s", err)
            return False

    async def async_set_ev_charge_ctrl(self, control: str) -> bool:
        """Start or stop EV charging ('START' or 'STOP')."""
        if not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return False

        url = f"{API_EV_URL}/{self.ev_charger_sn}/events"
        payload = {"control": control}
        try:
            async with self._session.post(url, json=payload, headers=self._get_auth_headers()) as resp:
                return resp.status == 200
        except Exception as err:
            _LOGGER.error("Failed to set charge control state '%s': %s", control, err)
            return False