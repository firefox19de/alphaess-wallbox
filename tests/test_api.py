"""Tests for the AlphaESS API client."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alphaess_wallbox.api import AlphaWebApiClient


def test_module_imports():
    """Regressionstest: Das Paket sollte ohne zusätzliche Pfad-Hacks importierbar sein."""
    assert AlphaWebApiClient is not None


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
