import base64
import hashlib
import logging
import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

_LOGGER = logging.getLogger(__name__)

def encrypt_password(password: str, username: str) -> str:
    """Portierung der CryptoJS AES-CBC Verschluesselung aus Node.js."""
    key = hashlib.sha256(username.encode("utf-8")).digest()
    iv = hashlib.md5(username.encode("utf-8")).digest()
    
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(password.encode("utf-8"), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)
    
    return base64.b64encode(encrypted_bytes).decode("utf-8")


class AlphaWebApiClient:
    """Client fuer die inoffizielle AlphaESS Cloud Web-API."""

    def __init__(self, username: str, password: str, base_url: str = "https://eurcloud.alphaess.com"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        return self._session

    async def close(self) -> None:
        """Schliesst die aiohttp Session sauber."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Fuehrt den 3-stufigen Login-Prozess mit AES-CBC Verschluesselung aus."""
        session = await self._get_session()
        
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Client-End": "Web",
            "System": "alphacloud",
            "platform": "AK9D8H",
            "Language": "de-DE",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            # Step 1: Session Cookie Handshake
            await session.post(f"{self.base_url}/login", headers=headers, timeout=10)

            # Step 2: Pilot Check
            pilot_url = f"{self.base_url}/api/usercenter/cloud/user/pilot"
            await session.post(pilot_url, json={"username": self.username, "pilot": False}, headers=headers, timeout=10)

            # Step 3: Login mit AES-CBC verschluesseltem Passwort
            login_url = f"{self.base_url}/api/usercenter/cloud/user/login"
            encrypted_pwd = encrypt_password(self.password, self.username)
            
            payload = {
                "username": self.username,
                "password": encrypted_pwd
            }

            async with session.post(login_url, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 200 or (data.get("data") and data["data"].get("token")):
                        self._token = data["data"]["token"]
                        _LOGGER.info("AlphaESS Web API Login erfolgreich!")
                        return True
                    _LOGGER.error("AlphaESS Login fehlgeschlagen mit Payload: %s", data)
                    return False

                _LOGGER.error("AlphaESS Web API Login fehlgeschlagen: Status %s", response.status)
                return False

        except Exception as err:
            _LOGGER.error("Fehler beim Login an AlphaESS Web-API: %s", err)
            return False

    async def set_charging_current(self, sys_sn: str, current: int) -> bool:
        """Setzt die Stromstaerke in Ampere."""
        return await self._send_command("/api/iterate/newEv/setNewEv", {"sysSn": sys_sn, "current": current})

    async def set_phases(self, sys_sn: str, phases: int) -> bool:
        """Setzt die Phasenanzahl (1 oder 3)."""
        return await self._send_command("/api/iterate/newEv/setNewEv", {"sysSn": sys_sn, "phases": phases})

    async def set_charge_mode(self, sys_sn: str, mode: int) -> bool:
        """Setzt den Lademodus."""
        return await self._send_command("/api/iterate/newEv/setNewEv", {"sysSn": sys_sn, "mode": mode})

    async def _send_command(self, endpoint: str, payload: dict) -> bool:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Client-End": "Web",
            "System": "alphacloud",
            "platform": "AK9D8H",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["token"] = self._token

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status in (401, 403):  # Token abgelaufen -> Re-Login
                if await self.login():
                    headers["Authorization"] = f"Bearer {self._token}"
                    headers["token"] = self._token
                    async with session.post(url, json=payload, headers=headers) as retry_res:
                        return retry_res.status == 200
            return response.status == 200