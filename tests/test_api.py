"""Tests for the AlphaESS API client."""
import base64
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alphaess_wallbox.api import AlphaWebApiClient, _hash_password


class MockResponse:
    def __init__(self, status=200, payload=None, text_body=""):
        self.status = status
        self._payload = payload
        self._text_body = text_body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return self._text_body


class AsyncCallWrapper:
    def __init__(self, response):
        self.response = response

    def __await__(self):
        async def _inner():
            return self.response

        return _inner().__await__()

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_module_imports():
    """Regressionstest: Das Paket sollte ohne zusätzliche Pfad-Hacks importierbar sein."""
    assert AlphaWebApiClient is not None


def test_hash_password_is_sha256_base64():
    """_hash_password muss SHA-256 gehasht und Base64-enkodiert zurückgeben."""
    password = "test_pass"
    expected = base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()
    assert _hash_password(password) == expected


def test_hash_password_not_plaintext():
    """Das gehashte Passwort darf niemals dem Klartext entsprechen."""
    assert _hash_password("geheim123") != "geheim123"


@pytest.mark.asyncio
async def test_login_stores_token_field():
    """Login muss das 'token'-Feld (neue API) aus der Antwort speichern."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "user@test.com", "pass")

    mock_session = MagicMock()
    mock_session.post = MagicMock(
        side_effect=lambda *args, **kwargs: AsyncCallWrapper(
            MockResponse(status=200, payload={"token": "my-access-token", "refreshToken": "my-refresh"})
        )
    )
    client._get_session = AsyncMock(return_value=mock_session)

    result = await client.login()

    assert result is True
    assert client._token == "my-access-token"


@pytest.mark.asyncio
async def test_login_sends_hashed_password():
    """Login muss das Passwort als SHA-256/Base64-Hash senden, nicht im Klartext."""
    password = "geheim123"
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "user@test.com", password)
    captured_payload = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_payload.update(json or {})
        return AsyncCallWrapper(MockResponse(status=200, payload={"token": "tok"}))

    mock_session = MagicMock()
    mock_session.post = fake_post
    client._get_session = AsyncMock(return_value=mock_session)

    await client.login()

    sent_password = captured_payload.get("password", "")
    assert sent_password != password
    assert sent_password == _hash_password(password)


@pytest.mark.asyncio
async def test_login_409_deletes_session_and_retries():
    """Bei HTTP 409 muss die alte Session per DELETE gelöscht und danach neu eingeloggt werden."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "user@test.com", "pass")

    call_count = {"post": 0, "delete": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        call_count["post"] += 1
        if call_count["post"] == 1:
            return AsyncCallWrapper(MockResponse(status=409, payload={}))
        return AsyncCallWrapper(MockResponse(status=200, payload={"token": "new-token"}))

    def fake_delete(url, headers=None, timeout=None):
        call_count["delete"] += 1
        return AsyncCallWrapper(MockResponse(status=204))

    mock_session = MagicMock()
    mock_session.post = fake_post
    mock_session.delete = fake_delete
    client._get_session = AsyncMock(return_value=mock_session)

    result = await client.login()

    assert result is True
    assert client._token == "new-token"
    assert call_count["post"] == 2, "POST muss zweimal aufgerufen werden"
    assert call_count["delete"] == 1, "DELETE muss einmal aufgerufen werden"


@pytest.mark.asyncio
async def test_login_returns_false_for_non_successful_status():
    """Login sollte bei fehlerhaften HTTP-Antworten sauber fehlschlagen."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "test_user", "test_pass")

    mock_session = MagicMock()
    mock_session.post = MagicMock(
        side_effect=lambda *args, **kwargs: AsyncCallWrapper(MockResponse(status=500, payload={})))
    client._get_session = AsyncMock(return_value=mock_session)

    result = await client.login()

    assert result is False
    assert client._token is None


@pytest.mark.asyncio
async def test_request_clears_token_when_refresh_login_fails():
    """Ein fehlerhaftes Token-Refresh sollte den alten Token nicht weiter verwenden."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "test_user", "test_pass")
    client._token = "stale-token"

    mock_session = MagicMock()
    mock_session.request = MagicMock(
        side_effect=lambda *args, **kwargs: AsyncCallWrapper(MockResponse(status=401, payload={})))
    client._get_session = AsyncMock(return_value=mock_session)
    client.login = AsyncMock(return_value=False)

    result = await client._request("GET", "/test")

    assert result is None
    assert client._token is None


@pytest.mark.asyncio
async def test_load_system_and_charger_from_devices_in_site():
    """Geräte-SNs sollen direkt aus dem 'devices'-Array im Sites-Objekt gelesen werden (neue API)."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "u", "p")
    client._token = "tok"
    client._request = AsyncMock(return_value=[
        {
            "id": "qGuKtccdRL6URCui2w",
            "devices": [
                {"type": "Ess", "sysSn": "ALB002022080906"},
                {"type": "EvCharger", "sysSn": "ALP2021082020071"},
            ],
        }
    ])

    result = await client.load_system_and_charger()

    assert result is True
    assert client.site_id == "qGuKtccdRL6URCui2w"
    assert client.system_sn == "ALB002022080906"
    assert client.ev_charger_sn == "ALP2021082020071"


@pytest.mark.asyncio
async def test_load_system_and_charger_returns_false_if_no_sites():
    """Gibt False zurück wenn /sites keine Daten liefert."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "u", "p")
    client._token = "tok"
    client._request = AsyncMock(return_value=[])

    assert await client.load_system_and_charger() is False


@pytest.mark.asyncio
async def test_load_system_and_charger_skips_if_already_loaded():
    """Zweiter Aufruf soll keine API-Requests machen wenn SNs bereits bekannt sind."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "u", "p")
    client.system_sn = "ESS123"
    client.ev_charger_sn = "EVC456"
    client._request = AsyncMock()

    assert await client.load_system_and_charger() is True
    client._request.assert_not_called()


@pytest.mark.asyncio
async def test_get_wallbox_status_success():
    """Testet, ob der Status korrekt aus der neuen v1-API-Antwort extrahiert wird."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "test_user", "test_pass")
    client.system_sn = "mock_system_sn"
    client.ev_charger_sn = "mock_charger_sn"
    client.load_system_and_charger = AsyncMock(return_value=True)

    client._request = AsyncMock(side_effect=[
        # GET /ev-charger/{sn}/real-status
        {"mode": 1},
        # GET /ess/{sn}?components=evCharger
        {
            "evCharger": {
                "g1T_chargeCurrent": 16,
                "g1T_chargeMode": 4,
                "g1T_obcPhase": 3,
            }
        },
    ])

    status = await client.get_wallbox_status()

    assert status is not None
    assert status["status_code"] == 1
    assert status["max_current"] == 16
    assert status["charging_mode"] == 4
    assert status["phase"] == 3
    assert status["charger_sn"] == "mock_charger_sn"


@pytest.mark.asyncio
async def test_get_wallbox_status_returns_none_if_no_charger():
    """Gibt None zurück wenn load_system_and_charger fehlschlägt."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "u", "p")
    client.load_system_and_charger = AsyncMock(return_value=False)

    assert await client.get_wallbox_status() is None
