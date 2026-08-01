"""Tests for the AlphaESS API client."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alphaess_wallbox.api import AlphaWebApiClient


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
async def test_get_wallbox_status_success():
    """Testet, ob der Status korrekt aus der simulierten API-Antwort extrahiert wird."""
    mock_hass = MagicMock()
    client = AlphaWebApiClient(mock_hass, "test_user", "test_pass")

    # Initialisierung überspringen, um den Status-Request isoliert zu testen
    client.system_sn = "mock_system_sn"
    client.ev_charger_sn = "mock_charger_sn"

    client.load_system_and_charger = AsyncMock(return_value=True)

    client._request = AsyncMock(side_effect=[
        {"data": {"mode": 1}},  # getChargPileStatusByPileSn
        {                        # get_ev_data
            "data": {
                "oldPileData": {
                    "maxCurrent": 16,
                    "chargingmode": 4,
                    "chargingpilePhase": 3
                }
            }
        }
    ])

    status = await client.get_wallbox_status()

    # Validierung der extrahierten Werte
    assert status is not None
    assert status["max_current"] == 16
    assert status["charging_mode"] == 4
    assert status["phase"] == 3
    assert status["status_code"] == 1
    assert status["charger_sn"] == "mock_charger_sn"
