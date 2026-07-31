import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

class AlphaWebApiClient:
    """Client fÃ¼r die inoffizielle AlphaESS Cloud Web-API."""

    def __init__(self, username: str, password: str, base_url: str = "https://eurcloud.alphaess.com"):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """SchlieÃt die aiohttp Session sauber."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Meldet sich an der Web-API an und holt die Session/Token."""
        session = await self._get_session()
        login_url = f"{self.base_url}/api/Account/Login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with session.post(login_url, json=payload, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == 200 or data.get("success"):
                        self._token = data.get("data", {}).get("accessToken")
                        _LOGGER.info("AlphaESS Web API Login erfolgreich!")
                        return True
            _LOGGER.error("AlphaESS Web API Login fehlgeschlagen: Status %s", response.status)
            return False
        except Exception as err:
            _LOGGER.error("Fehler beim Login an AlphaESS Web-API: %s", err)
            return False

    async def set_charging_current(self, sys_sn: str, current: int) -> bool:
        """Setzt die StromstÃ¤rke in Ampere."""
        return await self._send_command("/api/EVCharger/SetCurrent", {"sysSn": sys_sn, "current": current})

    async def set_phases(self, sys_sn: str, phases: int) -> bool:
        """Setzt die Phasenanzahl (1 oder 3)."""
        return await self._send_command("/api/EVCharger/SetPhases", {"sysSn": sys_sn, "phases": phases})

    async def set_charge_mode(self, sys_sn: str, mode: int) -> bool:
        """Setzt den Lademodus (1=Langsam, 2=Schon, 3=Schnell, 4=Custom)."""
        return await self._send_command("/api/EVCharger/SetMode", {"sysSn": sys_sn, "mode": mode})

    async def _send_command(self, endpoint: str, payload: dict) -> bool:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}

        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 401:  # Token abgelaufen -> Re-Login
                if await self.login():
                    headers = {"Authorization": f"Bearer {self._token}"}
                    async with session.post(url, json=payload, headers=headers) as retry_res:
                        return retry_res.status == 200
            return response.status == 200