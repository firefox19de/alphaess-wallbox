import asyncio
import base64
import hashlib
import json
import logging

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

_LOGGER = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Passwort mit SHA-256 hashen und Base64-enkodieren (neue API-Anforderung)."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


class AlphaWebApiClient:
    """Client für die neue AlphaESS Platform API (platform-eur.alphaess.com)."""

    def __init__(self, hass: HomeAssistant, username: str, password: str, base_url: str = "https://platform-eur.alphaess.com"):
        self.hass = hass
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session = None
        self._token: str | None = None

        self.system_sn: str | None = None
        self.site_id: str | None = None
        self.ev_charger_sn: str | None = None

    async def _get_session(self):
        if self._session is None:
            self._session = async_create_clientsession(self.hass)
        return self._session

    async def close(self) -> None:
        return

    def _get_headers(self) -> dict:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Tenant": "alphaess",
            "Client-End": "Web",
            "Client-Name": "Portal",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def login(self) -> bool:
        """Login über Platform Session Endpoint – Passwort wird SHA-256/Base64 gehasht."""
        self._token = None
        session = await self._get_session()
        headers = self._get_headers()

        login_url = f"{self.base_url}/api/users-center/sessions"
        payload = {
            "type": "password",
            "email": self.username,
            "password": _hash_password(self.password),
        }

        try:
            async with session.post(login_url, json=payload, headers=headers, timeout=10) as response:
                if response.status in (200, 201):
                    data = await response.json(content_type=None)
                    # API liefert "token" (access token) und "refreshToken"
                    token = data.get("token") or data.get("accessToken") or data.get("access_token")
                    if token:
                        self._token = token
                        _LOGGER.info("AlphaESS Platform Login erfolgreich!")
                        return True
                    _LOGGER.error("Kein Access-Token in Antwort empfangen: %s", data)
                    return False
                _LOGGER.error("AlphaESS Login fehlgeschlagen mit Status: %s", response.status)
                return False
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler beim API-Login an AlphaESS Platform: %s", err)
            return False

    async def _request(self, method: str, endpoint: str, json_payload: dict | None = None, params: dict | None = None) -> dict | list | None:
        if not self._token:
            if not await self.login():
                return None

        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            async with session.request(method, url, json=json_payload, params=params, headers=headers, timeout=10) as response:
                if response.status in (401, 403):
                    _LOGGER.warning("Token abgelaufen, führe Re-Login aus...")
                    self._token = None
                    if await self.login():
                        headers = self._get_headers()
                        async with session.request(method, url, json=json_payload, params=params, headers=headers, timeout=10) as retry_res:
                            return await self._parse_response(retry_res)
                    return None

                return await self._parse_response(response)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler bei API-Request an AlphaESS: %s", err)
            return None

    async def _parse_response(self, response) -> dict | list | None:
        if response.status not in (200, 201, 204):
            _LOGGER.warning("AlphaESS API Fehler-Status %s: %s", response.status, await response.text())
            return None
        if response.status == 204:
            return {"code": 200, "success": True}
        try:
            return await response.json(content_type=None)
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.error("AlphaESS JSON-Parse Fehler: %s", err)
            return None

    async def load_system_and_charger(self) -> bool:
        """Lädt Site ID, System-SN und Wallbox-Seriennummer aus den v1-Endpoints.

        Neue API: Die /sites-Antwort enthält ein 'devices'-Array mit allen Geräten direkt.
        Fallback auf den alten /devices-Endpunkt falls nötig.
        """
        if self.system_sn and self.ev_charger_sn:
            return True

        sites_res = await self._request("GET", "/api/internal/v1/sites")

        # Antwort kann direkt eine Liste oder in einem Wrapper-Objekt sein
        if isinstance(sites_res, dict):
            sites_list = sites_res.get("data") or sites_res.get("records") or sites_res.get("sites") or []
        elif isinstance(sites_res, list):
            sites_list = sites_res
        else:
            sites_list = []

        if not sites_list:
            _LOGGER.error("Keine AlphaESS Sites gefunden. Antwort: %s", sites_res)
            return False

        first_site = sites_list[0]
        # Neue API: Site-ID ist das 'id'-Feld (alphanumerischer Hash, z.B. qGuKtccdRL6URCui2w)
        self.site_id = (
            first_site.get("id")
            or first_site.get("sysId")
            or first_site.get("siteId")
        )

        # Neue API: Geräte-SNs direkt aus dem 'devices'-Array in der Sites-Antwort
        devices_in_site = first_site.get("devices") or []
        for dev in devices_in_site:
            dev_type = (dev.get("type") or "").lower()
            if dev_type == "ess" and not self.system_sn:
                self.system_sn = dev.get("sysSn")
            elif dev_type == "evcharger" and not self.ev_charger_sn:
                self.ev_charger_sn = dev.get("sysSn")

        # Fallback: alter /devices-Endpunkt
        if (not self.system_sn or not self.ev_charger_sn) and self.site_id:
            _LOGGER.debug("Geräte nicht in Sites-Antwort, versuche /devices-Endpunkt...")
            devices_res = await self._request("GET", f"/api/internal/v1/sites/{self.site_id}/devices")
            if devices_res and isinstance(devices_res, list):
                for dev in devices_res:
                    dev_type = (dev.get("type") or "").lower()
                    if "ess" in dev_type and not self.system_sn:
                        self.system_sn = dev.get("sysSn")
                    elif ("evcharger" in dev_type or "charger" in dev_type) and not self.ev_charger_sn:
                        self.ev_charger_sn = dev.get("sysSn")

        # Fallback: ESS-Endpunkt mit evCharger-Komponente
        if not self.ev_charger_sn and self.system_sn:
            _LOGGER.debug("Wallbox-SN nicht gefunden, versuche ESS evCharger-Komponente...")
            ess_res = await self._request(
                "GET",
                f"/api/internal/v1/ess/{self.system_sn}",
                params={"components": "evCharger"},
            )
            if ess_res and isinstance(ess_res, dict):
                ev_info = ess_res.get("evCharger") or {}
                self.ev_charger_sn = ev_info.get("sysSn") or ev_info.get("sn")

        _LOGGER.info(
            "Site-ID: %s | System-SN: %s | Wallbox-SN: %s",
            self.site_id, self.system_sn, self.ev_charger_sn,
        )
        return bool(self.system_sn and self.ev_charger_sn)

    async def get_wallbox_status(self) -> dict | None:
        """Holt Live-Status und aktuelle Einstellungen aus der v1 API."""
        if not await self.load_system_and_charger():
            return None

        real_status = await self._request("GET", f"/api/internal/v1/ev-charger/{self.ev_charger_sn}/real-status")
        ess_status = await self._request("GET", f"/api/internal/v1/ess/{self.system_sn}", params={"components": "evCharger"})

        ev_info = (ess_status.get("evCharger") if isinstance(ess_status, dict) else {}) or {}

        status_code = real_status.get("mode", 9) if isinstance(real_status, dict) else 9
        max_current = ev_info.get("g1T_chargeCurrent") or ev_info.get("maxCurrent", 16)
        phase = ev_info.get("g1T_obcPhase") or ev_info.get("chargingpilePhase", 3)
        charging_mode = ev_info.get("g1T_chargeMode") or ev_info.get("chargingmode", 4)

        return {
            "status_code": int(status_code),
            "max_current": int(float(max_current)),
            "phase": int(phase),
            "charging_mode": int(charging_mode),
            "charger_sn": self.ev_charger_sn,
        }

    async def set_charging_current(self, ampere: int) -> bool:
        """Setzt die Stromstärke via PATCH auf das ESS."""
        return await self._patch_ess_settings({"g1T_chargeCurrent": float(ampere)})

    async def set_phases(self, phases: int) -> bool:
        """Setzt die Phasenanzahl via PATCH auf das ESS."""
        return await self._patch_ess_settings({"g1T_obcPhase": int(phases)})

    async def set_charge_mode(self, mode_code: int) -> bool:
        """Setzt den Lademodus via PATCH auf das ESS."""
        return await self._patch_ess_settings({"g1T_chargeMode": int(mode_code)})

    async def _patch_ess_settings(self, updates: dict) -> bool:
        """Sendet gezielte Einstellungs-Updates per PATCH-Request."""
        if not await self.load_system_and_charger():
            return False

        res = await self._request("PATCH", f"/api/internal/v1/ess/{self.system_sn}", json_payload=updates)
        return res is not None