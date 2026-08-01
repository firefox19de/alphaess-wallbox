"""Tests for the AlphaESS API client."""
import pytest
from unittest.mock import AsyncMock

from custom_components.alphaess_wallbox.api import AlphaWebApiClient

@pytest.mark.asyncio
async def test_get_wallbox_status_success():
    """Testet, ob der Status korrekt aus der simulierten API-Antwort extrahiert wird."""
    client = AlphaWebApiClient("test_user", "test_pass")
    
    # Initialisierung überspringen, um den Status-Request isoliert zu testen
    client.system_sn = "mock_system_sn"
    client.ev_charger_sn = "mock_charger_sn"
    
    # Mock für den internen HTTP-Request (verhindert echte Netzwerkaufrufe)
    client._request = AsyncMock(return_value={
        "data": {
            "max_current": 16,
            "charging_mode": 4,
            "phase": 3
        }
    })

    status = await client.get_wallbox_status()

    # Validierung der extrahierten Werte
    assert status is not None
    assert status["max_current"] == 16
    assert status["charging_mode"] == 4
    assert status["phase"] == 3