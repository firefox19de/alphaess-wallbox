import base64
import hashlib
import logging
import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

_LOGGER = logging.getLogger(__name__)

def encrypt_password(password: str, username: str) -> str:
    """Portierung der CryptoJS AES-CBC Verschlüsselung aus Node.js."""
    # Key = SHA256(username) (32 Bytes)
    key = hashlib.sha256(username.encode("utf-8")).digest()
    
    # IV = MD5(username) (16 Bytes)
    iv = hashlib.md5(username.encode("utf-8")).digest()
    
    # AES-CBC mit PKCS7 Padding
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(password.encode("utf-8"), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)
    
    return base64.b64encode(encrypted_bytes).decode("utf-8")


class AlphaWebApiClient:
    def __init__(self, username: str, password: str, base_url: str = "https://eurcloud.alphaess.com"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # CookieJar ist notwendig, da AlphaESS Cookies verwendet
            self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())
        return self._session

    async def login(self) -> bool:
        """Führt den 3-stufigen Login-Prozess mit verschlüsseltem Passwort aus."""
        session = await self._get_session()
        
        # Identische Header wie im Node.js Skript
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
            # Schritt 1: Cookie/Session holen
            await session.post(f"{self.base_url}/login", headers=headers, timeout=10)

            # Schritt 2: Pilot Check
            pilot_url = f"{self.base_url}/api/usercenter/cloud/user/pilot"
            await session.post(pilot_url, json={"username": self.username, "pilot": False}, headers=headers, timeout=10)

            # Schritt 3: Eigentlicher Login mit verschlüsseltem Passwort
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
                
                _LOGGER.error("AlphaESS Login HTTP-Status %s", response.status)
                return False

        except Exception as err:
            _LOGGER.error("Fehler beim AlphaESS Login: %s", err)
            return False