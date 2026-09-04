import asyncio
import base64
import hashlib
import json
import logging
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Passwort mit SHA-256 hashen und Base64-enkodieren."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


class AlphaWebApiClient:
    """Client für die neue AlphaESS Platform API (platform-eur.alphaess.com)."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        base_url: str = "https://platform-eur.alphaess.com",
    ):
        self.hass = hass
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")

        self._token: str | None = None
        self._auth_lock = asyncio.Lock()  # Mutex gegen 409 Concurrent Login Errors

        self.system_sn: str | None = None
        self.site_id: str | None = None
        self.ev_charger_sn: str | None = None

    def _get_session(self):
        return async_get_clientsession(self.hass)

    async def close(self) -> None:
        """No-op for HA managed session."""
        return

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Tenant": "alphaess",
            "Client-End": "Web",
            "Client-Name": "Portal",
            "countryCode": "DE",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def login(self) -> bool:
        """Login über Platform Session Endpoint."""
        async with self._auth_lock:
            if self._token:
                return True

            session = self._get_session()
            login_url = f"{self.base_url}/api/users-center/sessions"
            payload = {
                "type": "password",
                "email": self.username,
                "password": _hash_password(self.password),
            }

            try:
                _LOGGER.debug("Führe Login bei AlphaESS Platform aus...")
                async with session.post(login_url, json=payload, headers=self._get_headers(), timeout=10) as response:
                    if response.status in (200, 201):
                        data = await response.json(content_type=None)
                        token = data.get("token") or data.get("accessToken")
                        if token:
                            self._token = token
                            _LOGGER.info("AlphaESS Platform Login erfolgreich!")
                            return True

                    if response.status in (400, 401, 403):
                        raise ConfigEntryAuthFailed("Zugangsdaten ungültig")

                    if response.status == 409:
                        _LOGGER.warning("Session existiert bereits (409). Reset per DELETE...")
                        async with session.delete(login_url, json=payload, headers=self._get_headers(), timeout=10):
                            pass
                        await asyncio.sleep(2.0)
                        async with session.post(login_url, json=payload, headers=self._get_headers(), timeout=10) as retry:
                            if retry.status in (200, 201):
                                data = await retry.json(content_type=None)
                                self._token = data.get("token") or data.get("accessToken")
                                return bool(self._token)

                    _LOGGER.error("AlphaESS Login fehlgeschlagen: Status %s", response.status)
                    return False
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error("Fehler beim API-Login: %s", err)
                return False

    async def _request(
        self, method: str, endpoint: str, json_payload: dict | None = None, params: dict | None = None
    ) -> dict | list | None:
        if not self._token:
            if not await self.login():
                return None

        session = self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(
                method, url, json=json_payload, params=params, headers=self._get_headers(), timeout=10
            ) as response:
                if response.status in (401, 403):
                    _LOGGER.warning("Token abgelaufen, erneuere Session...")
                    self._token = None
                    if await self.login():
                        async with session.request(
                            method, url, json=json_payload, params=params, headers=self._get_headers(), timeout=10
                        ) as retry_res:
                            return await self._parse_response(retry_res)
                    return None

                return await self._parse_response(response)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler beim API-Request (%s): %s", endpoint, err)
            return None

    async def _parse_response(self, response) -> dict | list | None:
        if response.status not in (200, 201, 204):
            _LOGGER.warning("API Antwort mit Status %s: %s", response.status, await response.text())
            return None
        if response.status == 204:
            return {"code": 200, "success": True}
        try:
            return await response.json(content_type=None)
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.error("JSON Parse Fehler: %s", err)
            return None

    async def load_system_and_charger(self) -> bool:
        """Ermittelt Site-ID, System-SN und Wallbox-SN."""
        if self.system_sn and self.ev_charger_sn:
            return True

        sites_res = await self._request("GET", "/api/internal/v1/sites")
        sites_list = sites_res if isinstance(sites_res, list) else (sites_res.get("data") if isinstance(sites_res, dict) else [])

        if not sites_list:
            _LOGGER.error("Keine AlphaESS Sites gefunden")
            return False

        first_site = sites_list[0]
        self.site_id = first_site.get("id") or first_site.get("sysId")

        devices = first_site.get("devices") or []
        for dev in devices:
            dev_type = (dev.get("type") or "").lower()
            if dev_type == "ess" and not self.system_sn:
                self.system_sn = dev.get("sysSn")
            elif dev_type == "evcharger" and not self.ev_charger_sn:
                self.ev_charger_sn = dev.get("sysSn")

        if not self.system_sn or not self.ev_charger_sn:
            devices_res = await self._request("GET", f"/api/internal/v1/sites/{self.site_id}/devices")
            if isinstance(devices_res, list):
                for dev in devices_res:
                    dev_type = (dev.get("type") or "").lower()
                    if "ess" in dev_type and not self.system_sn:
                        self.system_sn = dev.get("sysSn")
                    elif ("evcharger" in dev_type or "charger" in dev_type) and not self.ev_charger_sn:
                        self.ev_charger_sn = dev.get("sysSn")

        _LOGGER.info("System SN: %s | Wallbox SN: %s", self.system_sn, self.ev_charger_sn)
        return bool(self.system_sn and self.ev_charger_sn)

    async def get_wallbox_status(self) -> dict | None:
        """Liest den aktuellen Status der Wallbox aus."""
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
            "max_current": float(max_current),
            "phase": int(phase),
            "charging_mode": int(charging_mode),
            "charger_sn": self.ev_charger_sn,
        }

    async def set_charging_current(self, ampere: float) -> bool:
        """Setzt den Ladestrom per PATCH auf den Inverter (ESS)."""
        return await self._patch_ess_settings({"g1T_chargeCurrent": float(ampere)})

    async def set_phases(self, phases: int) -> bool:
        """Setzt die Phasen per PATCH auf den Inverter (ESS)."""
        return await self._patch_ess_settings({"g1T_obcPhase": int(phases)})

    async def set_charge_mode(self, mode_code: int) -> bool:
        """Setzt den Lademodus per PATCH auf den Inverter (ESS)."""
        return await self._patch_ess_settings({"g1T_chargeMode": int(mode_code)})

    async def _patch_ess_settings(self, updates: dict) -> bool:
        """Sendet gezielte Einstellungen per PATCH an den Wechselrichter."""
        if not await self.load_system_and_charger():
            return False

        res = await self._request("PATCH", f"/api/internal/v1/ess/{self.system_sn}", json_payload=updates)
        return res is not None