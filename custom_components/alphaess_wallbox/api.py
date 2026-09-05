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

        # Dauerhafter lokaler Zustandsspeicher
        self.last_known_config = {
            "chargeCurrent": 6.0,
            "chargeMode": 4,
            "obcPhase": 3,
        }

    async def async_login(self) -> bool:
        """Authenticate with AlphaESS cloud API."""
        try:
            await self._session.post(LOGIN_URL, headers=DEFAULT_HEADERS)

            pilot_payload = {"username": self._username, "pilot": False}
            await self._session.post(API_PILOT_URL, json=pilot_payload, headers=DEFAULT_HEADERS)

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

            async with self._session.get(API_SITES_URL, headers=headers) as resp:
                res_json = await resp.json()
                sites = _extract_data(res_json)
                if not isinstance(sites, list) or not sites:
                    _LOGGER.error("No sites found in AlphaESS account.")
                    return False
                self.site_id = sites[0].get("id")

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
        """Get real-time EV charger status merged with cached/fetched config."""
        if not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return dict(self.last_known_config)

        result = dict(self.last_known_config)
        headers = self._get_auth_headers()

        # 1. Real-time Status
        status_url = f"{API_EV_URL}/{self.ev_charger_sn}/real-status"
        try:
            async with self._session.get(status_url, headers=headers) as resp:
                res_json = await resp.json()
                data = _extract_data(res_json)
                if isinstance(data, dict):
                    result.update({
                        "status": data.get("status"),
                        "gun_is_lock": data.get("gunIsLock"),
                        "power": data.get("power"),
                    })
        except Exception as err:
            _LOGGER.error("Failed to fetch EV charger status: %s", err)

        # 2. Config/g1T aus Devices-Endpunkt extrahieren (nur überschreiben, wenn ungleich None)
        devices_url = f"{API_SITES_URL}/{self.site_id}/devices"
        try:
            async with self._session.get(devices_url, headers=headers) as resp:
                res_json = await resp.json()
                devices_data = _extract_data(res_json)
                if isinstance(devices_data, dict):
                    ess_list = devices_data.get("ess", [])
                    if ess_list and isinstance(ess_list, list) and len(ess_list) > 0:
                        ev_chargers = ess_list[0].get("evChargers", [])
                        if ev_chargers and isinstance(ev_chargers, list) and len(ev_chargers) > 0:
                            g1t = ev_chargers[0].get("g1T", {})
                            if isinstance(g1t, dict):
                                if g1t.get("chargeCurrent") is not None:
                                    self.last_known_config["chargeCurrent"] = float(g1t["chargeCurrent"])
                                if g1t.get("chargeMode") is not None:
                                    self.last_known_config["chargeMode"] = int(g1t["chargeMode"])
                                if g1t.get("obcPhase") is not None:
                                    self.last_known_config["obcPhase"] = int(g1t["obcPhase"])
                            result.update(self.last_known_config)
        except Exception as err:
            _LOGGER.debug("Could not fetch g1T config from site devices: %s", err)

        return result

    async def _patch_g1t_config(self, g1t_payload: dict) -> bool:
        """Helper method to PATCH EV charger g1T parameters."""
        if not self.system_sn or not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return False

        url = f"{API_ESS_URL}/{self.system_sn}"
        payload = {
            "evCharger": [
                {
                    "sn": self.ev_charger_sn,
                    "g1T": g1t_payload
                }
            ]
        }
        try:
            async with self._session.patch(url, json=payload, headers=self._get_auth_headers()) as resp:
                if resp.status in (200, 204):
                    # Bei Erfolg Zustand lokal in der Instanz sichern
                    for key, val in g1t_payload.items():
                        if key in self.last_known_config:
                            self.last_known_config[key] = val
                    return True
                text = await resp.text()
                _LOGGER.error("PATCH g1T failed (HTTP %s): %s", resp.status, text)
                return False
        except Exception as err:
            _LOGGER.error("Error during PATCH g1T config: %s", err)
            return False

    async def async_set_ev_charge_current(self, current: float) -> bool:
        """Set charge current (6.0 - 16.0 A in 0.1 steps)."""
        val = int(current) if current.is_integer() else round(current, 1)
        return await self._patch_g1t_config({"chargeCurrent": val})

    async def async_set_ev_charge_mode(self, mode: int) -> bool:
        """Set charge mode (1=Eco-Slow, 2=Eco-General, 3=Eco-Quick, 4=Power)."""
        return await self._patch_g1t_config({"chargeMode": int(mode)})

    async def async_set_ev_phases(self, phases: int) -> bool:
        """Set OBC phases (1, 2 or 3)."""
        return await self._patch_g1t_config({"obcPhase": int(phases)})