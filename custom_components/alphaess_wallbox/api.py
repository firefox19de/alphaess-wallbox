import asyncio
import base64
from datetime import datetime
import hashlib
import json
import logging

from aiohttp import ClientError
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

_LOGGER = logging.getLogger(__name__)


def encrypt_password(password: str, username: str) -> str:
    """Portierung der CryptoJS AES-CBC Verschlüsselung aus Node.js."""
    key = hashlib.sha256(username.encode("utf-8")).digest()
    iv = hashlib.md5(username.encode("utf-8")).digest()

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(password.encode("utf-8"), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)

    return base64.b64encode(encrypted_bytes).decode("utf-8")


class AlphaWebApiClient:
    """Client für die AlphaESS Cloud Web-API."""

    def __init__(self, hass: HomeAssistant, username: str, password: str, base_url: str = "https://eurcloud.alphaess.com"):
        self.hass = hass
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session = None
        self._token: str | None = None

        self.system_sn: str | None = None
        self.ev_charger_id: str = "EV1"
        self.ev_charger_key: str | None = None
        self.ev_charger_sn: str | None = None

    async def _get_session(self):
        if self._session is None:
            self._session = async_create_clientsession(self.hass)
        return self._session

    async def close(self) -> None:
        """No-op for HA managed aiohttp sessions."""
        return

    def _get_headers(self) -> dict:
        now = datetime.now()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Client-End": "Web",
            "System": "alphacloud",
            "platform": "AK9D8H",
            "Language": "de-DE",
            "X-Requested-With": "XMLHttpRequest",
            "operationDate": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["token"] = self._token
        return headers

    async def login(self) -> bool:
        """Führt den 3-stufigen Login-Prozess aus."""
        self._token = None
        session = await self._get_session()
        headers = self._get_headers()

        try:
            await session.post(f"{self.base_url}/login", headers=headers, timeout=10)

            pilot_url = f"{self.base_url}/api/usercenter/cloud/user/pilot"
            await session.post(pilot_url, json={"username": self.username, "pilot": False}, headers=headers, timeout=10)

            login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
            encrypted_pwd = encrypt_password(self.password, self.username)
            payload = {"username": self.username, "password": encrypted_pwd}

            async with session.post(login_url, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    try:
                        data = await response.json(content_type=None)
                    except (json.JSONDecodeError, ValueError) as err:
                        _LOGGER.error(
                            "AlphaESS Login konnte Antwort nicht parsen: %s", err)
                        return False

                    if data.get("code") == 200 or (data.get("data") and data["data"].get("token")):
                        self._token = data["data"]["token"]
                        _LOGGER.info("AlphaESS Web API Login erfolgreich!")
                        return True
                    _LOGGER.error(
                        "AlphaESS Login fehlgeschlagen mit Payload: %s", data)
                    return False
                _LOGGER.error(
                    "AlphaESS Web API Login fehlgeschlagen: Status %s", response.status)
                return False
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler beim Login an AlphaESS Web-API: %s", err)
            return False

    async def _request(self, method: str, endpoint: str, json_payload: dict | None = None, params: dict | None = None) -> dict | None:
        if not self._token:
            if not await self.login():
                return None

        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            async with session.request(method, url, json=json_payload, params=params, headers=headers, timeout=10) as response:
                if response.status in (401, 403):
                    _LOGGER.warning("Token abgelaufen, erneuere Session...")
                    self._token = None
                    if await self.login():
                        headers = self._get_headers()
                        async with session.request(method, url, json=json_payload, params=params, headers=headers, timeout=10) as retry_res:
                            return await self._parse_response(retry_res)
                    return None

                return await self._parse_response(response)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fehler beim API-Request an AlphaESS: %s", err)
            return None

    async def _parse_response(self, response) -> dict | None:
        if response.status != 200:
            _LOGGER.warning("AlphaESS API Antwort mit Status %s: %s", response.status, await response.text())
            return None

        try:
            data = await response.json(content_type=None)
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.error(
                "AlphaESS API Antwort konnte nicht geparst werden: %s", err)
            return None

        return data

    async def load_system_and_charger(self) -> bool:
        """Lädt System-SN und Wallbox-Details."""
        if self.system_sn and self.ev_charger_sn:
            return True

        system_data = await self._request("GET", "/api/stable/home/getCustomMenuEssList")
        if not system_data or not system_data.get("data"):
            _LOGGER.error("Kein AlphaESS System gefunden")
            return False

        self.system_sn = system_data["data"][0]["sysSn"]

        ev_data = await self._request("GET", "/api/iterate/newEv/getNewEvBySn", params={"sysSn": self.system_sn})
        if not ev_data or not ev_data.get("data"):
            _LOGGER.error("Keine Wallbox-Daten gefunden")
            return False

        raw_data = ev_data["data"]
        old_pile_data = raw_data.get("oldPileData") or raw_data

        self.ev_charger_id = old_pile_data.get("chargingpileId", "EV1")
        self.ev_charger_key = old_pile_data.get("chargingpileKey")
        self.ev_charger_sn = old_pile_data.get("chargingpileSn")

        _LOGGER.info("System SN: %s | Wallbox SN: %s",
                     self.system_sn, self.ev_charger_sn)
        return True

    async def get_ev_data(self) -> dict | None:
        """Holt die aktuellen Wallbox-Rohdaten."""
        if not await self.load_system_and_charger():
            return None
        res = await self._request("GET", "/api/iterate/newEv/getNewEvBySn", params={"sysSn": self.system_sn})
        return res.get("data") if res else None

    async def get_wallbox_status(self) -> dict | None:
        """Liest den aktuellen Live-Status der Wallbox aus."""
        if not await self.load_system_and_charger():
            return None

        status_res = await self._request(
            "GET",
            "/api/iterate/ev/v2/getChargPileStatusByPileSn",
            params={"sysSn": self.system_sn,
                    "chargingpileId": self.ev_charger_id}
        )
        ev_data = await self.get_ev_data()
        if not ev_data:
            return None

        old_pile_data = ev_data.get("oldPileData") or ev_data
        status_code = status_res.get("data", {}).get(
            "mode", 9) if status_res else 9

        return {
            "status_code": status_code,
            "max_current": old_pile_data.get("maxCurrent", 0),
            "phase": old_pile_data.get("chargingpilePhase", 3),
            "charging_mode": old_pile_data.get("chargingmode", 4),
            "charger_sn": self.ev_charger_sn
        }

    async def set_charging_current(self, ampere: int) -> bool:
        """Setzt die maximale Stromstärke (A)."""
        return await self._update_ev_settings({"maxCurrent": ampere})

    async def set_phases(self, phases: int) -> bool:
        """Setzt die Phasenanzahl (1 oder 3)."""
        return await self._update_ev_settings({"chargingpilePhase": phases})

    async def set_charge_mode(self, mode_code: int) -> bool:
        """Setzt den Lademodus (1-4)."""
        return await self._update_ev_settings({"chargingmode": mode_code})

    async def _update_ev_settings(self, updates: dict) -> bool:
        """Baut das alte Payload-Objekt nach und sendet das Update an die Cloud."""
        ev_data = await self.get_ev_data()
        if not ev_data:
            return False

        old_pile_data = dict(ev_data.get("oldPileData") or ev_data)

        # Standardwerte beibehalten / aktualisieren
        old_pile_data.update({
            "chargingmode": old_pile_data.get("chargingmode", 4),
            "chargingpileSn": self.ev_charger_sn,
            "chargingpileSwitch": True,
            "chargingpilePhase": old_pile_data.get("chargingpilePhase", 3),
            "timeCharge1": False,
            "timeChargeS1": "00:00",
            "timeChargeE1": "23:59",
            "timeCharge2": False,
            "timeChargeS2": "00:00",
            "timeChargeE2": "00:00",
            "maxCurrent": old_pile_data.get("maxCurrent", 16)
        })

        # Gezielt veränderte Felder überschreiben
        old_pile_data.update(updates)

        payload = {
            "sysSn": self.system_sn,
            "isNewPile": False,
            "whetherToVerify": False,
            "chargingpileControlOpen": True,
            "currentsetting": ev_data.get("currentsetting", 32),
            "oldPileData": old_pile_data
        }

        res = await self._request("POST", "/api/iterate/newEv/setNewEv", json_payload=payload)
        return res is not None and res.get("code") == 200
