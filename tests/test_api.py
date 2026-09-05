"""Tests fuer den AlphaESS API-Client."""
import pytest
from unittest.mock import MagicMock

from custom_components.alphaess_wallbox.api import AlphaESSApiClient


class MockResponse:
    def __init__(self, status=200, payload=None, text_body=""):
        self.status = status
        self._payload = payload
        self._text_body = text_body
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def json(self, content_type=None): return self._payload
    async def text(self): return self._text_body


class AsyncCtx:
    """Dual-Mode: direkt await-bar UND als async-with nutzbar."""
    def __init__(self, response):
        self.response = response
    def __await__(self):
        async def _i(): return self.response
        return _i().__await__()
    async def __aenter__(self): return self.response
    async def __aexit__(self, *a): return False


def make_session(post_payload=None, get_payload=None, patch_status=200):
    s = MagicMock()
    s.post = MagicMock(return_value=AsyncCtx(MockResponse(200, post_payload)))
    s.get = MagicMock(return_value=AsyncCtx(MockResponse(200, get_payload)))
    s.patch = MagicMock(return_value=AsyncCtx(MockResponse(patch_status)))
    return s


def test_module_imports():
    assert AlphaESSApiClient is not None


@pytest.mark.asyncio
async def test_login_success():
    session = make_session(post_payload={"accessToken": "tok123", "refreshToken": "ref"})
    client = AlphaESSApiClient(session, "user@test.com", "pass")
    assert await client.async_login() is True
    assert client._access_token == "Bearer tok123"
    assert client._refresh_token == "ref"


@pytest.mark.asyncio
async def test_login_missing_token_returns_false():
    session = make_session(post_payload={"error": "bad"})
    client = AlphaESSApiClient(session, "u", "p")
    assert await client.async_login() is False
    assert client._access_token is None


@pytest.mark.asyncio
async def test_login_exception_returns_false():
    session = MagicMock()
    session.post = MagicMock(side_effect=Exception("Network error"))
    client = AlphaESSApiClient(session, "u", "p")
    assert await client.async_login() is False


@pytest.mark.asyncio
async def test_get_env_and_site_details_success():
    session = MagicMock()
    session.post = MagicMock(return_value=AsyncCtx(MockResponse(200, {"accessToken": "tok"})))
    sites_r = MockResponse(200, [{"id": "SITE1"}])
    site_r = MockResponse(200, {"hasChargingPile": True, "essDevices": [{"sysSn": "ESS123"}]})
    dev_r = MockResponse(200, {"ess": [{"evChargers": [{"sysSn": "EVC456"}]}]})
    session.get = MagicMock(side_effect=[AsyncCtx(sites_r), AsyncCtx(site_r), AsyncCtx(dev_r)])
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    assert await client.async_get_env_and_site_details() is True
    assert client.site_id == "SITE1"
    assert client.system_sn == "ESS123"
    assert client.ev_charger_sn == "EVC456"


@pytest.mark.asyncio
async def test_get_env_no_sites_returns_false():
    session = MagicMock()
    session.get = MagicMock(return_value=AsyncCtx(MockResponse(200, [])))
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    assert await client.async_get_env_and_site_details() is False


@pytest.mark.asyncio
async def test_get_ev_status_extracts_g1t():
    session = MagicMock()
    status_r = MockResponse(200, {"status": 2, "gunIsLock": False, "power": 3.3})
    dev_r = MockResponse(200, {"ess": [{"evChargers": [{"sysSn": "EVC", "g1T": {"chargeCurrent": 10, "chargeMode": 4, "obcPhase": 3}}]}]})
    session.get = MagicMock(side_effect=[AsyncCtx(status_r), AsyncCtx(dev_r)])
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    client.ev_charger_sn = "EVC"
    client.site_id = "SITE1"
    result = await client.async_get_ev_status()
    assert result["status"] == 2
    assert result["chargeCurrent"] == 10.0
    assert result["chargeMode"] == 4
    assert result["obcPhase"] == 3


@pytest.mark.asyncio
async def test_patch_g1t_success():
    session = MagicMock()
    session.patch = MagicMock(return_value=AsyncCtx(MockResponse(200)))
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    client.system_sn = "ESS"
    client.ev_charger_sn = "EVC"
    assert await client._patch_g1t({"chargeCurrent": 10}) is True


@pytest.mark.asyncio
async def test_patch_g1t_http_error_returns_false():
    session = MagicMock()
    session.patch = MagicMock(return_value=AsyncCtx(MockResponse(400, text_body="Bad")))
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    client.system_sn = "ESS"
    client.ev_charger_sn = "EVC"
    assert await client._patch_g1t({"chargeCurrent": 10}) is False


@pytest.mark.asyncio
async def test_set_ev_charge_current_integer():
    session = MagicMock()
    session.patch = MagicMock(return_value=AsyncCtx(MockResponse(200)))
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    client.system_sn = "ESS"
    client.ev_charger_sn = "EVC"
    assert await client.async_set_ev_charge_current(16.0) is True
    kw = session.patch.call_args
    payload = kw.kwargs.get("json") or kw.args[1]
    assert payload["evCharger"][0]["g1T"]["chargeCurrent"] == 16


@pytest.mark.asyncio
async def test_ev_start_sends_start_control():
    session = MagicMock()
    session.post = MagicMock(return_value=AsyncCtx(MockResponse(200)))
    client = AlphaESSApiClient(session, "u", "p")
    client._access_token = "Bearer tok"
    client.ev_charger_sn = "EVC"
    assert await client.async_ev_start() is True
    kw = session.post.call_args
    payload = kw.kwargs.get("json") or kw.args[1]
    assert payload["control"] == "START"
