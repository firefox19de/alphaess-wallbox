"""API Client for AlphaESS Wallbox - portiert von AlphaEVControlv2.js."""
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

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

EV_START = "START"
EV_STOP = "STOP"
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class AlphaESSApiClient:
    """Client fuer die AlphaESS Cloud v1-API (platform-eur.alphaess.com)."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self.site_id: str | None = None
        self.system_sn: str | None = None
        self.ev_charger_sn: str | None = None
        self.has_charging_pile: bool = False

    def _auth_headers(self) -> dict:
        headers = DEFAULT_HEADERS.copy()
        if self._access_token:
            headers["Authorization"] = self._access_token
        return headers

    @staticmethod
    def _unwrap(raw, key="data"):
        if isinstance(raw, dict) and key in raw:
            return raw[key]
        return raw
    async def async_login(self) -> bool:
        """3-stufiger Login-Prozess (login() aus dem JS)."""
        self._access_token = None
        self._refresh_token = None
        try:
            await self._session.post(LOGIN_URL, headers=DEFAULT_HEADERS, timeout=_TIMEOUT)
            await self._session.post(
                API_PILOT_URL,
                json={"username": self._username, "pilot": False},
                headers=DEFAULT_HEADERS,
                timeout=_TIMEOUT,
            )
            payload = {"type": "password", "email": self._username, "password": self._password}
            async with self._session.post(API_SESSION_URL, json=payload, headers=DEFAULT_HEADERS, timeout=_TIMEOUT) as resp:
                data = await resp.json(content_type=None)
            token_data = self._unwrap(data)
            access_token = token_data.get("accessToken") if isinstance(token_data, dict) else None
            if not access_token:
                _LOGGER.error("AlphaESS Login fehlgeschlagen - kein accessToken. Antwort: %s", data)
                return False
            self._access_token = f"Bearer {access_token}"
            self._refresh_token = token_data.get("refreshToken") if isinstance(token_data, dict) else None
            _LOGGER.info("AlphaESS Login erfolgreich.")
            return True
        except Exception as err:
            _LOGGER.error("Fehler beim AlphaESS Login: %s", err)
            return False

    async def async_get_env_and_site_details(self) -> bool:
        """Ermittelt site_id, system_sn und ev_charger_sn (getEnvDetails+getSiteDetails+getEVCharger)."""
        if not self._access_token:
            if not await self.async_login():
                return False
        try:
            async with self._session.get(API_SITES_URL, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                sites = self._unwrap(await resp.json(content_type=None))
            if not isinstance(sites, list) or not sites:
                _LOGGER.error("AlphaESS: Keine Sites gefunden.")
                return False
            self.site_id = sites[0].get("id")
            if not self.site_id:
                _LOGGER.error("AlphaESS: Site-ID fehlt: %s", sites[0])
                return False
            site_url = f"{API_SITES_URL}/{self.site_id}"
            async with self._session.get(site_url, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                site = self._unwrap(await resp.json(content_type=None))
            self.has_charging_pile = bool(site.get("hasChargingPile", False)) if isinstance(site, dict) else False
            ess_devices = site.get("essDevices", []) if isinstance(site, dict) else []
            if ess_devices:
                self.system_sn = ess_devices[0].get("sysSn")
            if not self.has_charging_pile:
                _LOGGER.error("AlphaESS: Keine Wallbox (hasChargingPile=False) am Site %s.", self.site_id)
                return False
            devices_url = f"{API_SITES_URL}/{self.site_id}/devices"
            async with self._session.get(devices_url, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                devices = self._unwrap(await resp.json(content_type=None))
            ess_list = devices.get("ess", []) if isinstance(devices, dict) else []
            ev_chargers = ess_list[0].get("evChargers", []) if ess_list else []
            if not ev_chargers:
                _LOGGER.error("AlphaESS: Keine evChargers gefunden.")
                return False
            self.ev_charger_sn = ev_chargers[0].get("sysSn")
            _LOGGER.info("AlphaESS Setup: site_id=%s | system_sn=%s | ev_charger_sn=%s", self.site_id, self.system_sn, self.ev_charger_sn)
            return True
        except Exception as err:
            _LOGGER.error("Fehler beim Laden der AlphaESS Site-Details: %s", err)
            return False
    async def async_get_ev_status(self) -> dict | None:
        """Liest Live-Status und g1T-Konfiguration (getEVStatus aus dem JS)."""
        if not self._access_token:
            if not await self.async_login():
                return None
        if not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return None
        result: dict = {}
        status_url = f"{API_EV_URL}/{self.ev_charger_sn}/real-status"
        try:
            async with self._session.get(status_url, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                status_data = self._unwrap(await resp.json(content_type=None))
            if isinstance(status_data, dict):
                result["status"] = status_data.get("status")
                result["gun_is_lock"] = status_data.get("gunIsLock")
                result["power"] = status_data.get("power")
        except Exception as err:
            _LOGGER.warning("Konnte EV-Status nicht abrufen: %s", err)
        if self.site_id:
            devices_url = f"{API_SITES_URL}/{self.site_id}/devices"
            try:
                async with self._session.get(devices_url, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                    devices = self._unwrap(await resp.json(content_type=None))
                ess_list = devices.get("ess", []) if isinstance(devices, dict) else []
                ev_chargers = ess_list[0].get("evChargers", []) if ess_list else []
                g1t = ev_chargers[0].get("g1T", {}) if ev_chargers else {}
                if isinstance(g1t, dict):
                    if g1t.get("chargeCurrent") is not None:
                        result["chargeCurrent"] = float(g1t["chargeCurrent"])
                    if g1t.get("chargeMode") is not None:
                        result["chargeMode"] = int(g1t["chargeMode"])
                    if g1t.get("obcPhase") is not None:
                        result["obcPhase"] = int(g1t["obcPhase"])
            except Exception as err:
                _LOGGER.debug("Konnte g1T-Konfiguration nicht abrufen: %s", err)
        return result if result else None

    async def _patch_g1t(self, g1t_payload: dict) -> bool:
        """PATCH /api/internal/v1/ess/{system_sn} mit g1T-Parametern (setEVChargeCurrent aus dem JS)."""
        if not self.system_sn or not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return False
        url = f"{API_ESS_URL}/{self.system_sn}"
        payload = {"evCharger": [{"sn": self.ev_charger_sn, "g1T": g1t_payload}]}
        try:
            async with self._session.patch(url, json=payload, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                if resp.status in (200, 204):
                    return True
                text = await resp.text()
                _LOGGER.error("PATCH g1T fehlgeschlagen (HTTP %s): %s", resp.status, text)
                return False
        except Exception as err:
            _LOGGER.error("Fehler beim PATCH g1T: %s", err)
            return False

    async def async_set_ev_charge_current(self, current: float) -> bool:
        """Setzt die Ladestromstaerke in Ampere (6-16 A)."""
        val: float | int = int(current) if float(current).is_integer() else round(current, 1)
        return await self._patch_g1t({"chargeCurrent": val})

    async def async_set_ev_charge_mode(self, mode: int) -> bool:
        """Setzt den Lademodus (1=Eco-Langsam, 2=Eco-Standard, 3=Eco-Schnell, 4=Leistung)."""
        return await self._patch_g1t({"chargeMode": int(mode)})

    async def async_set_ev_phases(self, phases: int) -> bool:
        """Setzt die Phasenzahl (1 oder 3)."""
        return await self._patch_g1t({"obcPhase": int(phases)})

    async def _ev_control(self, ctrl: str) -> bool:
        """POST /api/internal/v1/ev-charger/{sn}/events (setEVChargeCtrl aus dem JS)."""
        if not self.ev_charger_sn:
            if not await self.async_get_env_and_site_details():
                return False
        url = f"{API_EV_URL}/{self.ev_charger_sn}/events"
        try:
            async with self._session.post(url, json={"control": ctrl}, headers=self._auth_headers(), timeout=_TIMEOUT) as resp:
                if resp.status in (200, 201, 204):
                    return True
                text = await resp.text()
                _LOGGER.error("EV-Control '%s' fehlgeschlagen (HTTP %s): %s", ctrl, resp.status, text)
                return False
        except Exception as err:
            _LOGGER.error("Fehler beim EV-Control '%s': %s", ctrl, err)
            return False

    async def async_ev_start(self) -> bool:
        """Startet den Ladevorgang."""
        return await self._ev_control(EV_START)

    async def async_ev_stop(self) -> bool:
        """Stoppt den Ladevorgang."""
        return await self._ev_control(EV_STOP)
